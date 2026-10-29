"""Apply the spam limit table only when no other schema/data changes are pending."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Apply only the spam protection table and empty merges on PostgreSQL. Back up first."

    def handle(self, *args, **options):
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("Expected the production PostgreSQL database; no changes made.")
        executor = MigrationExecutor(connection)
        if executor.loader.detect_conflicts():
            raise CommandError("Resolve migration branches with makemigrations --merge --noinput first.")
        targets = executor.loader.graph.leaf_nodes("electricity")
        if len(targets) != 1:
            raise CommandError("Expected one electricity migration target; no changes made.")
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
        call_command("migrate", "electricity", targets[0][1], interactive=False)
