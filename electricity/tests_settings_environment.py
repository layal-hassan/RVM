import os
from pathlib import Path
import runpy
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings


class SettingsEnvironmentTests(SimpleTestCase):
    def load(self, **values):
        path = Path(__file__).resolve().parent.parent / "PRO" / "settings.py"
        environment = {"SECRET_KEY": "settings-test-secret", "ALLOWED_HOSTS": "localhost", **values}
        # Test the deployed values independently of this checkout's private .env.
        with patch.dict(os.environ, environment, clear=True), patch("pathlib.Path.exists", return_value=False):
            return runpy.run_path(str(path))

    def test_production_ignores_legacy_debug_flag_and_accepts_both_domains(self):
        values = self.load(DEBUG="True", USE_POSTGRES="true", DB_NAME="rwmel")
        self.assertFalse(values["DEBUG"])
        self.assertEqual(values["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        with override_settings(ALLOWED_HOSTS=values["ALLOWED_HOSTS"]):
            for domain in ("rwmel.se", "www.rwmel.se"):
                self.assertEqual(RequestFactory().get("/faq/", HTTP_HOST=domain).get_host(), domain)
        self.assertIn("https://rwmel.se", values["CSRF_TRUSTED_ORIGINS"])

    def test_local_debug_requires_explicit_development_environment(self):
        values = self.load(DJANGO_ENV="development", DEBUG="true")
        self.assertTrue(values["DEBUG"])
        self.assertIn("rwmel.se", values["ALLOWED_HOSTS"])

    def test_explicit_production_cannot_enable_debug(self):
        values = self.load(DJANGO_ENV="production", DEBUG="true")
        self.assertFalse(values["DEBUG"])
