from unittest.mock import Mock, patch

from django.core import mail
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings
from django.urls import reverse

from .email_backend import company_email_recipients, send_company_email
from .models import AutomatedEmailTemplate, OnCallBooking, ServiceRequestOutsideArea
from .views import _send_automated_workflow_emails, _send_booking_company_notification_email, _send_on_call_company_notification_email


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SECURE_SSL_REDIRECT=False,
    CONTACT_TO_EMAIL="info@example.com", BOOKING_TO_EMAIL="services@example.com",
    SUPPORT_TO_EMAIL="support@example.com", CAREERS_TO_EMAIL="careers@example.com",
)
class CompanyEmailDeliveryTests(TestCase):
    def send_booking(self, label="Service Booking"):
        _send_booking_company_notification_email(
            booking_reference="RWM-123", booking_type_label=label,
            customer_name="Customer", customer_email="customer@example.com",
            customer_phone="0701234567", address="Stockholm", summary_lines=["Requested work"],
        )

    def test_each_type_resolves_to_its_company_mailbox(self):
        for workflow in ("contact", "quote", "quick_quote", "feedback"):
            self.assertEqual(company_email_recipients(workflow), ["info@example.com"])
        for workflow in ("consultation", "electrician", "service", "on_call"):
            self.assertEqual(company_email_recipients(workflow), ["services@example.com"])
        self.assertEqual(company_email_recipients("support"), ["support@example.com"])
        self.assertEqual(company_email_recipients("careers"), ["careers@example.com"])

    def test_company_recipients_support_multiple_addresses_without_duplicates(self):
        self.assertEqual(company_email_recipients("contact", "Info <info@example.com>, other@example.com, INFO@example.com"), ["info@example.com", "other@example.com"])

    def test_zero_messages_sent_is_not_reported_as_success(self):
        message = EmailMessage("Company test", "Body", "support@example.com", ["info@example.com"])
        with patch.object(message, "send", return_value=0):
            with self.assertRaisesMessage(RuntimeError, "did not accept"):
                send_company_email(message)

    def test_automated_booking_workflows_default_to_services(self):
        result = _send_automated_workflow_emails("service", {"name": "Customer", "email": "customer@example.com"})
        self.assertEqual(result["company"], "sent")
        self.assertEqual(mail.outbox[0].to, ["services@example.com"])
        self.assertEqual(mail.outbox[1].reply_to, ["services@example.com"])

    def test_company_failure_does_not_skip_customer_confirmation(self):
        with patch("electricity.views.send_company_email", side_effect=RuntimeError("SMTP failure")):
            with self.assertLogs("electricity.views", level="ERROR"):
                result = _send_automated_workflow_emails("quick_quote", {"email": "customer@example.com"})
        self.assertEqual(result, {"company": "failed", "customer": "sent"})
        self.assertEqual(mail.outbox[0].to, ["customer@example.com"])

    def test_all_booking_helpers_honor_configured_company_recipient(self):
        for workflow, label in (("consultation", "Consultation Booking"), ("electrician", "Electrician Booking"), ("service", "Service Booking")):
            with self.subTest(workflow=workflow):
                AutomatedEmailTemplate.objects.filter(workflow=workflow).update(company_recipient=f"{workflow}@example.com")
                self.send_booking(label)
                self.assertEqual(mail.outbox[-1].to, [f"{workflow}@example.com"])
        AutomatedEmailTemplate.objects.filter(workflow="on_call").update(company_recipient="oncall@example.com")
        _send_on_call_company_notification_email(booking=OnCallBooking.objects.create(), booking_reference="OC-123")
        self.assertEqual(mail.outbox[-1].to, ["oncall@example.com"])

    def test_disabled_company_booking_emails_are_not_sent(self):
        AutomatedEmailTemplate.objects.filter(workflow__in=["service", "on_call"]).update(company_enabled=False)
        self.send_booking()
        _send_on_call_company_notification_email(booking=OnCallBooking.objects.create(), booking_reference="OC-123")
        self.assertEqual(len(mail.outbox), 0)

    def test_outside_area_request_saves_notification_and_emails_services(self):
        response = self.client.post(reverse("electricity:outside_area", kwargs={"flow": "service", "zip_code": "99999"}), {
            "full_name": "Outside Customer", "email": "outside@example.com", "phone": "0701234567", "details": "Please install lighting.",
        })
        self.assertEqual(response.status_code, 200)
        record = ServiceRequestOutsideArea.objects.get()
        self.assertTrue(record.admin_notifications.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["services@example.com"])
        self.assertIn("99999", mail.outbox[0].body)
        self.assertIn("Please install lighting.", mail.outbox[0].body)
