from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings

from .email_backend import EmailBackend, invoice_email_connection, support_email_connection


@override_settings(
    EMAIL_BACKEND="electricity.email_backend.EmailBackend",
    EMAIL_HOST="smtp.example.com",
    EMAIL_PORT=587,
    EMAIL_USE_TLS=True,
    EMAIL_USE_SSL=False,
    SUPPORT_EMAIL_HOST_USER="support@example.com",
    SUPPORT_EMAIL_HOST_PASSWORD="test-support-password",
    INVOICE_EMAIL_HOST_USER="billing@example.com",
    INVOICE_EMAIL_HOST_PASSWORD="test-billing-password",
)
class SMTPAccountRoutingTests(SimpleTestCase):
    def test_custom_backend_authenticates_each_role_with_its_own_account(self):
        # Exercise Django's SMTP login and envelope generation without network I/O.
        with patch("electricity.email_backend.ChunkedSMTP") as smtp:
            for factory, address, password in (
                (support_email_connection, "support@example.com", "test-support-password"),
                (invoice_email_connection, "billing@example.com", "test-billing-password"),
            ):
                smtp.reset_mock()
                connection = factory()
                self.assertIsInstance(connection, EmailBackend)
                message = EmailMessage(
                    "Website enquiry", "Test message", address, ["info@example.com"],
                    reply_to=["customer@example.net"], connection=connection,
                )
                self.assertEqual(message.send(), 1)
                smtp.return_value.starttls.assert_called_once()
                smtp.return_value.login.assert_called_once_with(address, password)
                sender, recipients, payload = smtp.return_value.sendmail.call_args.args
                self.assertEqual(sender, address)
                self.assertEqual(recipients, ["info@example.com"])
                self.assertIn(b"Reply-To: customer@example.net", payload)
                self.assertIn(("From: " + address).encode(), payload)

    @override_settings(SUPPORT_EMAIL_HOST_PASSWORD="")
    def test_incomplete_role_account_fails_without_using_another_account(self):
        with self.assertRaises(ImproperlyConfigured):
            support_email_connection()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_non_smtp_backend_keeps_default_test_connection(self):
        self.assertIsNone(support_email_connection())
        self.assertIsNone(invoice_email_connection())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
    def test_standard_smtp_backend_also_uses_role_credentials(self):
        connection = support_email_connection()
        self.assertEqual(connection.username, "support@example.com")
        self.assertEqual(connection.password, "test-support-password")
