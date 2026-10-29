"""Apply only the independent spam limit migration, preserving other pending work."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Apply only the spam protection table on PostgreSQL. Back up first."

    def handle(self, *args, **options):
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("Expected the production PostgreSQL database; no changes made.")
        executor = MigrationExecutor(connection)
        if executor.loader.detect_conflicts():
            raise CommandError("Resolve migration branches with makemigrations --merge --noinput first.")
        # A leaf merge can pull in unrelated template/data migrations. Target
        # the independent table explicitly, without advancing the other branch.
        target = ("electricity", "0058_publicformsubmissionbucket")
        if target in executor.loader.applied_migrations:
            if "electricity_publicformsubmissionbucket" not in connection.introspection.table_names():
                raise CommandError("Migration is recorded but the protection table is missing; no changes made.")
            self.stdout.write(self.style.SUCCESS("Spam protection migration is already applied; no changes made."))
            return
        targets = [target]
        for migration, backwards in executor.migration_plan(targets):
            allowed = not backwards and migration.app_label == "electricity" and all(
                isinstance(operation, migrations.CreateModel)
                and operation.name.lower() == "publicformsubmissionbucket"
                and migration.name == "0058_publicformsubmissionbucket"
                for operation in migration.operations
            )
            if not allowed:
                raise CommandError(
                    f"Other changes are pending: {migration.app_label}.{migration.name}. "
                    "No migrations were applied. Review migrate --plan before proceeding."
                )
        call_command("migrate", "electricity", target[1], interactive=False)
