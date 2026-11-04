"""Run from the production service environment, once a minute or as a worker."""

import time
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from electricity.email_outbox import retry_due_company_emails


class Command(BaseCommand):
    help = "Retry due company notifications only; accepted messages and customer confirmations are excluded."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Maximum messages per batch (1-500).")
        parser.add_argument("--watch", action="store_true", help="Continue checking every 30 seconds; stop with Ctrl+C.")
        parser.add_argument("--print-systemd-unit", action="store_true", help="On the VPS, print a worker service matching the rwmel service user and this Python interpreter; installs nothing.")

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 500:
            raise CommandError("--limit must be between 1 and 500.")
        if options["print_systemd_unit"]:
            if sys.platform != "linux":
                raise CommandError("Generate the service on the Linux VPS using its active virtualenv.")
            user = subprocess.check_output(["systemctl", "show", "rwmel", "--property=User", "--value"], text=True).strip()
            if not user or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in user):
                raise CommandError("The rwmel service must have an explicit, valid User before generating the worker service.")
            def quote(value):
                value = str(value)
                if "\n" in value or "\r" in value:
                    raise CommandError("Service paths must not contain newlines.")
                return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'
            self.stdout.write(
                "[Unit]\nDescription=RWM EL company email retry worker\n"
                "After=network-online.target rwmel.service\nWants=network-online.target\n\n"
                f"[Service]\nType=simple\nUser={user}\n"
                f"WorkingDirectory={quote(settings.BASE_DIR)}\n"
                f"ExecStart={quote(sys.executable)} {quote(Path(settings.BASE_DIR) / 'service_manage.py')} retry_company_emails --watch --limit {options['limit']}\n"
                "Restart=on-failure\nRestartSec=10\nUMask=0077\n\n"
                "[Install]\nWantedBy=multi-user.target"
            )
            return
        try:
            while True:
                close_old_connections()
                result = retry_due_company_emails(options["limit"])
                self.stdout.write(f"Selected: {result['selected']}; accepted by mail backend: {result['accepted']}.")
                if not options["watch"]:
                    break
                time.sleep(30)
        except KeyboardInterrupt:
            self.stdout.write("Company email retry worker stopped.")
