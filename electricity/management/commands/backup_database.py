"""Back up the configured PostgreSQL database without modifying its records."""

import datetime
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Back up the configured PostgreSQL database to a private pg_dump archive."

    def add_arguments(self, parser):
        parser.add_argument("--directory", default="/var/backups")

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError("Expected PostgreSQL. No backup or database changes were attempted.")
        executable = shutil.which("pg_dump")
        if not executable:
            raise CommandError("pg_dump is not installed. No database changes were attempted.")
        directory = Path(options["directory"])
        if not directory.is_dir():
            raise CommandError("Backup directory does not exist.")
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = directory / f"rwmel-postgres-{stamp}-{uuid.uuid4().hex[:8]}.dump"
        environment = os.environ.copy()
        if database.get("PASSWORD"):
            environment["PGPASSWORD"] = str(database["PASSWORD"])
        command = [executable, "--format=custom", "--no-password"]
        for option, key in (("--host", "HOST"), ("--port", "PORT"), ("--username", "USER")):
            if database.get(key):
                command.extend([option, str(database[key])])
        command.extend(["--dbname", str(database["NAME"])])
        # O_EXCL and mode 0600 keep the archive unique and private.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                subprocess.run(command, env=environment, stdout=output, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CommandError(f"Backup failed; incomplete archive at {path}. No database changes were made.") from exc
        self.stdout.write(self.style.SUCCESS(f"PostgreSQL backup saved: {path}"))
