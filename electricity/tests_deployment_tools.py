import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import migrations
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, override_settings

import service_manage


class ServiceManagementTests(SimpleTestCase):
    def run_wrapper(self, environment, files="", working_directory=None):
        root = Path(service_manage.__file__).resolve().parent
        values = {
            "WorkingDirectory": str(root) if working_directory is None else working_directory,
            "EnvironmentFiles": files, "Environment": environment,
        }
        def output(command, **kwargs):
            return values[command[-2].split("=", 1)[1]]
        with patch("sys.argv", ["service_manage.py", "check"]), patch(
            "service_manage.subprocess.check_output", side_effect=output,
        ), patch("service_manage.os.chdir"), patch("service_manage.os.execve") as execute:
            service_manage.main()
            return execute.call_args

    def test_commands_use_service_credentials_without_shell_interpretation(self):
        with patch.dict(os.environ, {"DB_PASSWORD": "wrong-shell-password"}):
            call = self.run_wrapper('USE_POSTGRES=true DB_NAME=rwmel "DB_PASSWORD=test $literal secret"')
        self.assertEqual(call.args[2]["DB_NAME"], "rwmel")
        self.assertEqual(call.args[2]["DB_PASSWORD"], "test $literal secret")
        self.assertEqual(call.args[1][-1], "check")

    def test_missing_service_db_settings_cannot_fall_back_to_shell_values(self):
        with patch.dict(os.environ, {"USE_POSTGRES": "true", "DB_NAME": "wrong"}):
            with self.assertRaises(SystemExit):
                self.run_wrapper("")

    def test_unresolved_environment_files_or_different_checkouts_are_rejected(self):
        for options in ({"files": "/etc/rwmel.env"}, {"working_directory": "/different/checkout"}):
            with self.subTest(options=options), self.assertRaises(SystemExit):
                self.run_wrapper("USE_POSTGRES=true DB_NAME=rwmel", **options)


class PostgreSQLBackupTests(SimpleTestCase):
    def test_explicit_dump_path_is_used_when_service_path_is_incomplete(self):
        configuration = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "rwmel"}}
        executable = "/usr/lib/postgresql/14/bin/pg_dump"
        with tempfile.TemporaryDirectory() as directory, override_settings(DATABASES=configuration):
            with patch("shutil.which", return_value=executable) as locate, patch("subprocess.run") as run:
                call_command("backup_database", directory=directory, pg_dump=executable)
            locate.assert_called_once_with(executable)
            self.assertEqual(run.call_args.args[0][0], executable)

    def test_missing_executable_does_not_start_dump_or_create_archive(self):
        configuration = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "rwmel"}}
        with tempfile.TemporaryDirectory() as directory, override_settings(DATABASES=configuration):
            with patch("shutil.which", return_value=None), patch("subprocess.run") as run, self.assertRaises(CommandError):
                call_command("backup_database", directory=directory)
            run.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_sqlite_is_rejected_without_creating_backup(self):
        with self.assertRaises(CommandError), patch("subprocess.run") as run:
            call_command("backup_database")
        run.assert_not_called()

    def test_postgres_archive_is_private_and_password_is_only_passed_in_environment(self):
        configuration = {"default": {
            "ENGINE": "django.db.backends.postgresql", "NAME": "rwmel",
            "HOST": "localhost", "PORT": "5432", "USER": "app",
            "PASSWORD": "test-private-password",
        }}
        with tempfile.TemporaryDirectory() as directory, override_settings(DATABASES=configuration):
            def dump(command, **kwargs):
                self.assertNotIn("test-private-password", command)
                self.assertEqual(kwargs["env"]["PGPASSWORD"], "test-private-password")
                kwargs["stdout"].write(b"PGDMP-test-archive")
            with patch("shutil.which", return_value="pg_dump"), patch("subprocess.run", side_effect=dump):
                call_command("backup_database", directory=directory, verbosity=0)
            archives = list(Path(directory).glob("*.dump"))
            self.assertEqual(len(archives), 1)
            self.assertEqual(archives[0].read_bytes(), b"PGDMP-test-archive")
            if os.name != "nt":
                self.assertEqual(archives[0].stat().st_mode & 0o777, 0o600)

    def test_failed_dump_is_reported_as_failure(self):
        configuration = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "rwmel"}}
        with tempfile.TemporaryDirectory() as directory, override_settings(DATABASES=configuration):
            with patch("shutil.which", return_value="pg_dump"), patch(
                "subprocess.run", side_effect=subprocess.CalledProcessError(1, "pg_dump"),
            ), self.assertRaises(CommandError):
                call_command("backup_database", directory=directory)


class GuardedSpamMigrationTests(SimpleTestCase):
    def run_guard(self, plan):
        from .management.commands.apply_spam_protection import Command
        module = "electricity.management.commands.apply_spam_protection"
        with patch(module + ".settings") as settings, patch(module + ".MigrationExecutor") as executor, patch(module + ".call_command") as migrate:
            settings.DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql"}}
            executor.return_value.loader.detect_conflicts.return_value = {}
            executor.return_value.loader.applied_migrations = {}
            executor.return_value.migration_plan.return_value = plan
            Command().handle()
            executor.return_value.migration_plan.assert_called_once_with([
                ("electricity", "0058_publicformsubmissionbucket"),
            ])
            return migrate.call_args

    def test_new_limit_table_and_empty_merge_are_allowed(self):
        table = migrations.Migration("0058_publicformsubmissionbucket", "electricity")
        table.operations = [migrations.CreateModel("PublicFormSubmissionBucket", [])]
        merge = migrations.Migration("0059_merge", "electricity")
        call = self.run_guard([(table, False), (merge, False)])
        self.assertEqual(call.args, ("migrate", "electricity", "0058_publicformsubmissionbucket"))
        self.assertFalse(call.kwargs["interactive"])

    def test_data_changes_and_rollback_are_rejected(self):
        migration = migrations.Migration("0057_other_changes", "electricity")
        migration.operations = [migrations.RunPython(migrations.RunPython.noop)]
        with self.assertRaises(CommandError):
            self.run_guard([(migration, False)])
        merge = migrations.Migration("0059_merge", "electricity")
        with self.assertRaises(CommandError):
            self.run_guard([(merge, True)])

    def test_table_migration_does_not_depend_on_workflow_or_template_updates(self):
        loader = MigrationLoader(None)
        plan = loader.graph.forwards_plan(("electricity", "0058_publicformsubmissionbucket"))
        self.assertIn(("electricity", "0054_automatedemailtemplate"), plan)
        for name in (
            "0055_align_customer_facing_pricing", "0055_expand_automated_email_workflows",
            "0056_update_service_email_template", "0057_update_service_email_next_steps",
        ):
            self.assertNotIn(("electricity", name), plan)
        self.assertEqual(loader.detect_conflicts(), {})

    def test_already_applied_table_does_not_roll_back_later_migrations(self):
        from .management.commands.apply_spam_protection import Command
        module = "electricity.management.commands.apply_spam_protection"
        with patch(module + ".settings") as settings, patch(module + ".MigrationExecutor") as executor, patch(module + ".call_command") as migrate, patch(module + ".connection") as connection:
            settings.DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql"}}
            executor.return_value.loader.detect_conflicts.return_value = {}
            executor.return_value.loader.applied_migrations = {("electricity", "0058_publicformsubmissionbucket"): object()}
            connection.introspection.table_names.return_value = ["electricity_publicformsubmissionbucket"]
            Command().handle()
            migrate.assert_not_called()
            executor.return_value.migration_plan.assert_not_called()
