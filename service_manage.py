"""Run a Django command with the production systemd service's environment.

Linux deployment usage: python service_manage.py check
Service defaults to rwmel. Credentials are passed in memory, never printed.
"""

import os
from pathlib import Path
import shlex
import subprocess
import sys


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python service_manage.py <Django command> [arguments]")
    service = "rwmel"
    root = Path(__file__).resolve().parent

    def service_value(property_name):
        return subprocess.check_output(
            ["systemctl", "show", service, "--property=" + property_name, "--value"],
            text=True,
        ).strip()

    working_directory = service_value("WorkingDirectory")
    if not working_directory or Path(working_directory).resolve() != root:
        raise SystemExit("Service working directory does not match this checkout; no command was run.")
    # EnvironmentFile values can override Environment. Refuse to silently omit
    # them; this deployment currently configures its DB directly in Environment.
    if service_value("EnvironmentFiles"):
        raise SystemExit("Service uses EnvironmentFiles; resolve those settings before using this wrapper.")
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("DB_") and key not in {"USE_POSTGRES", "DJANGO_SETTINGS_MODULE"}
    }
    for item in shlex.split(service_value("Environment")):
        key, separator, value = item.partition("=")
        if separator:
            environment[key] = value
    if environment.get("USE_POSTGRES", "").lower() not in {"true", "1", "yes"} or not environment.get("DB_NAME"):
        raise SystemExit("Production PostgreSQL settings are missing; refusing to fall back to SQLite.")
    os.chdir(root)
    os.execve(sys.executable, [sys.executable, str(root / "manage.py"), *sys.argv[1:]], environment)


if __name__ == "__main__":
    main()
