import datetime
import io
import smtplib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .email_backend import send_company_email
from .email_outbox import MAX_ATTEMPTS, RETRY_DELAYS, attempt_company_email, retry_due_company_emails
from .models import CompanyEmailDelivery
from .views import _send_automated_workflow_emails


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SECURE_SSL_REDIRECT=False)
class CompanyEmailOutboxTests(TestCase):
    def message(self):
        message = EmailMessage("Company request", "Original request body", "support@example.com", ["info@example.com"], reply_to=["customer@example.com"])
        message.attach("request.pdf", b"%PDF-original-attachment", "application/pdf")
        return message

    def fail_message(self, error=None):
        message = self.message()
        with patch.object(message, "send", side_effect=error or OSError("SMTP temporarily unavailable")):
            with self.assertRaises(Exception):
                send_company_email(message)
        return CompanyEmailDelivery.objects.latest("created_at")

    def make_due(self, delivery):
        CompanyEmailDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now() - datetime.timedelta(seconds=1))

    def test_accepted_message_is_recorded_and_never_retried(self):
        self.assertEqual(send_company_email(self.message()), 1)
        delivery = CompanyEmailDelivery.objects.get()
        self.assertEqual(delivery.status, CompanyEmailDelivery.Status.ACCEPTED)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(bytes(delivery.payload), b"")
        self.assertEqual(retry_due_company_emails(), {"selected": 0, "accepted": 0})
        self.assertEqual(attempt_company_email(delivery.pk), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_failure_is_saved_with_attachment_and_delayed_retry(self):
        before = timezone.now()
        delivery = self.fail_message()
        self.assertEqual(delivery.status, CompanyEmailDelivery.Status.PENDING)
        self.assertEqual(delivery.attempts, 1)
        self.assertGreaterEqual(delivery.next_attempt_at, before + datetime.timedelta(seconds=60))
        self.assertIn(b"request.pdf", bytes(delivery.payload))
        self.assertEqual(retry_due_company_emails()["selected"], 0)

    def test_successful_retry_preserves_original_mime_message_and_envelope(self):
        delivery = self.fail_message()
        original_payload = bytes(delivery.payload)
        self.make_due(delivery)
        self.assertEqual(retry_due_company_emails(), {"selected": 1, "accepted": 1})
        outgoing = mail.outbox[0]
        self.assertEqual(outgoing.to, ["info@example.com"])
        self.assertEqual(outgoing.message()["Reply-To"], "customer@example.com")
        self.assertEqual(outgoing.message()["Message-ID"], delivery.message_id)
        self.assertEqual(outgoing.message().as_bytes(linesep="\r\n"), original_payload)
        attachment = next(part for part in outgoing.message().walk() if part.get_filename())
        self.assertEqual(attachment.get_payload(decode=True), b"%PDF-original-attachment")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, CompanyEmailDelivery.Status.ACCEPTED)
        self.assertEqual(delivery.attempts, 2)
        self.assertIsNotNone(delivery.accepted_at)

    @override_settings(
        EMAIL_BACKEND="electricity.email_backend.EmailBackend", EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
        SUPPORT_EMAIL_HOST_USER="support@example.com", SUPPORT_EMAIL_HOST_PASSWORD="test-password",
    )
    def test_retry_passes_original_mime_to_authenticated_smtp_backend(self):
        delivery = self.fail_message()
        self.make_due(delivery)
        with patch("electricity.email_backend.ChunkedSMTP") as smtp:
            self.assertEqual(retry_due_company_emails()["accepted"], 1)
        smtp.return_value.login.assert_called_once_with("support@example.com", "test-password")
        sender, recipients, payload = smtp.return_value.sendmail.call_args.args
        self.assertEqual(sender, "support@example.com")
        self.assertEqual(recipients, ["info@example.com"])
        self.assertIn(delivery.message_id.encode(), payload)
        self.assertIn(b"request.pdf", payload)

    def test_retry_preserves_unicode_subject_body_and_attachment_name(self):
        message = self.message()
        message.subject = "طلب عرض سعر – Förfrågan"
        message.body = "يرجى مراجعة الطلب. Tack för hjälpen."
        message.attach("تفاصيل.txt", "بيانات الطلب", "text/plain")
        with patch.object(message, "send", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                send_company_email(message)
        delivery = CompanyEmailDelivery.objects.get()
        self.make_due(delivery)
        self.assertEqual(retry_due_company_emails()["accepted"], 1)
        mime = mail.outbox[0].message()
        self.assertEqual(str(mime["Subject"]), message.subject)
        body = next(part for part in mime.walk() if part.get_content_type() == "text/plain" and not part.get_filename())
        self.assertEqual(body.get_payload(decode=True).decode("utf-8"), message.body)
        self.assertIn("تفاصيل.txt", [part.get_filename() for part in mime.walk()])

    def test_missing_smtp_credentials_are_saved_before_account_creation(self):
        with patch("electricity.email_outbox.support_email_connection", side_effect=ImproperlyConfigured("credentials missing")):
            with self.assertRaises(ImproperlyConfigured):
                send_company_email(self.message())
        self.assertEqual(CompanyEmailDelivery.objects.get().status, CompanyEmailDelivery.Status.PENDING)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_console_backend_does_not_discard_email_as_successful(self):
        with self.assertRaises(ImproperlyConfigured):
            send_company_email(self.message())
        delivery = CompanyEmailDelivery.objects.get()
        self.assertEqual(delivery.status, CompanyEmailDelivery.Status.PENDING)
        self.assertTrue(bytes(delivery.payload))

    def test_worker_handoff_is_not_reported_as_accepted_before_delivery(self):
        with patch("electricity.email_outbox.attempt_company_email", return_value=0):
            with self.assertRaisesMessage(RuntimeError, "awaiting the retry worker"):
                send_company_email(self.message())
        self.assertEqual(CompanyEmailDelivery.objects.get().status, CompanyEmailDelivery.Status.PENDING)

    def test_worker_continues_after_failure_and_obeys_maximum_attempts(self):
        delivery = self.fail_message()
        for attempt in range(2, MAX_ATTEMPTS + 1):
            self.make_due(delivery)
            with patch("electricity.email_outbox._StoredEmail.send", side_effect=smtplib.SMTPAuthenticationError(535, b"sensitive server details")):
                result = retry_due_company_emails()
            self.assertEqual(result, {"selected": 1, "accepted": 0})
            delivery.refresh_from_db()
            self.assertEqual(delivery.attempts, attempt)
            self.assertEqual(delivery.last_error, "SMTPAuthenticationError (535)")
            if attempt < MAX_ATTEMPTS:
                self.assertEqual(delivery.status, CompanyEmailDelivery.Status.PENDING)
                self.assertGreater(delivery.next_attempt_at, timezone.now() + datetime.timedelta(seconds=RETRY_DELAYS[attempt - 1] - 2))
        self.assertEqual(delivery.status, CompanyEmailDelivery.Status.FAILED)
        self.assertIsNone(delivery.next_attempt_at)
        self.assertEqual(retry_due_company_emails()["selected"], 0)

    def test_active_claim_cannot_be_sent_by_a_second_worker(self):
        delivery = self.fail_message()
        self.make_due(delivery)
        def send_during_claim(*args, **kwargs):
            self.assertEqual(attempt_company_email(delivery.pk), 0)
            return 1
        with patch("electricity.email_outbox._StoredEmail.send", side_effect=send_during_claim) as sender:
            self.assertEqual(attempt_company_email(delivery.pk), 1)
        sender.assert_called_once()

    def test_crashed_worker_lease_is_recovered(self):
        delivery = self.fail_message()
        CompanyEmailDelivery.objects.filter(pk=delivery.pk).update(status="sending", locked_until=timezone.now() - datetime.timedelta(minutes=1))
        self.assertEqual(retry_due_company_emails()["accepted"], 1)

    def test_crash_on_final_attempt_becomes_needs_attention(self):
        delivery = self.fail_message()
        CompanyEmailDelivery.objects.filter(pk=delivery.pk).update(status="sending", attempts=MAX_ATTEMPTS, locked_until=timezone.now() - datetime.timedelta(minutes=1))
        self.assertEqual(retry_due_company_emails()["selected"], 0)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, CompanyEmailDelivery.Status.FAILED)

    def test_customer_confirmation_is_sent_once_while_company_retries(self):
        with patch("electricity.email_outbox.support_email_connection", side_effect=OSError("SMTP failure")):
            result = _send_automated_workflow_emails("quick_quote", {"email": "customer@example.com"})
        self.assertEqual(result, {"company": "failed", "customer": "sent"})
        self.assertEqual(len(mail.outbox), 1)
        delivery = CompanyEmailDelivery.objects.get()
        self.make_due(delivery)
        self.assertEqual(retry_due_company_emails()["accepted"], 1)
        self.assertEqual(sum(message.to == ["customer@example.com"] for message in mail.outbox), 1)

    def test_retry_command_processes_only_due_messages_and_validates_limit(self):
        delivery = self.fail_message()
        self.make_due(delivery)
        output = io.StringIO()
        call_command("retry_company_emails", limit=1, stdout=output)
        self.assertIn("Selected: 1; accepted by mail backend: 1", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("retry_company_emails", limit=0)

    def test_email_dashboard_shows_pending_delivery_without_exposing_payload(self):
        self.fail_message()
        staff = get_user_model().objects.create_user(username="outbox-staff", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("electricity:dashboard_email_templates"))
        self.assertContains(response, "Retry scheduled")
        self.assertContains(response, "Next retry")
        self.assertNotContains(response, "Original request body")

    def test_systemd_unit_uses_actual_interpreter_user_and_service_environment(self):
        output = io.StringIO()
        with patch("electricity.management.commands.retry_company_emails.sys.platform", "linux"), patch("electricity.management.commands.retry_company_emails.subprocess.check_output", return_value="www-data\n"):
            call_command("retry_company_emails", print_systemd_unit=True, stdout=output)
        self.assertIn("User=www-data", output.getvalue())
        self.assertIn("service_manage.py", output.getvalue())
        self.assertIn("--watch", output.getvalue())
        self.assertIn("Restart=on-failure", output.getvalue())
