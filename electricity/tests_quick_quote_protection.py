import datetime
from unittest.mock import patch

from django.core import mail, signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ConsultationRequest


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class QuickQuoteProtectionTests(TestCase):
    def payload(self, **overrides):
        response = self.client.get(reverse("electricity:home"))
        data = {
            "form_type": "quick_quote", "full_name": "أحمد Andersson",
            "email": "customer@example.com", "phone": "0701234567",
            "message": "Please inspect the fuse board.",
            "submission_token": response.context["quote_form"]["submission_token"].value(),
            "website": "",
        }
        data.update(overrides)
        return data

    def submit(self, data, **headers):
        return self.client.post(reverse("electricity:home"), data, **headers)

    def test_real_submission_saves_and_notifies_without_reflecting_customer_content(self):
        data = self.payload(message="Project information https://example.com/project")
        self.assertEqual(self.submit(data).status_code, 302)
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        confirmation = mail.outbox[1]
        self.assertEqual(confirmation.to, [data["email"]])
        for value in (data["full_name"], data["message"], data["phone"]):
            self.assertNotIn(value, confirmation.body)

    def test_advertising_link_in_name_is_rejected_before_save_or_send(self):
        response = self.submit(self.payload(full_name="Collect your reward https://tinyurl.com/example"))
        self.assertTrue(response.context["quote_form"].has_error("full_name"))
        self.assertEqual(ConsultationRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_and_missing_or_forged_tokens_are_rejected(self):
        for overrides in ({"website": "bot"}, {"submission_token": ""}, {"submission_token": "forged"}):
            with self.subTest(overrides=overrides):
                response = self.submit(self.payload(**overrides))
                self.assertTrue(response.context["quote_form"].errors)
        self.assertEqual(ConsultationRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_expired_token_is_rejected(self):
        old = timezone.now().timestamp() - 7201
        with patch("django.core.signing.time.time", return_value=old):
            token = signing.dumps("expired", salt="quick-quote-form")
        response = self.submit(self.payload(submission_token=token))
        self.assertTrue(response.context["quote_form"].has_error("submission_token"))
        self.assertEqual(len(mail.outbox), 0)

    def test_token_cannot_be_replayed(self):
        data = self.payload()
        self.assertEqual(self.submit(data).status_code, 302)
        self.assertEqual(self.submit(data).status_code, 429)
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_recipient_limit_is_shared_across_ip_addresses(self):
        for index in range(3):
            self.assertEqual(self.submit(self.payload(message=f"Project {index}"), REMOTE_ADDR=f"192.0.2.{index}").status_code, 302)
        response = self.submit(self.payload(message="Another project"), REMOTE_ADDR="192.0.2.100")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(ConsultationRequest.objects.count(), 3)
        self.assertEqual(len(mail.outbox), 6)

    def test_ip_limit_cannot_be_bypassed_by_forging_forwarded_for(self):
        for index in range(5):
            data = self.payload(email=f"customer{index}@example.com", phone=f"070123456{index}")
            self.assertEqual(self.submit(data).status_code, 302)
        response = self.submit(self.payload(email="other@example.com"), HTTP_X_FORWARDED_FOR="192.0.2.99")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(ConsultationRequest.objects.count(), 5)

    def test_limits_allow_new_submissions_after_window_expires(self):
        now = timezone.now()
        with patch("electricity.form_protection.timezone.now", return_value=now):
            for index in range(3):
                self.assertEqual(self.submit(self.payload(message=f"Project {index}")).status_code, 302)
            self.assertEqual(self.submit(self.payload(message="Another project")).status_code, 429)
        with patch("electricity.form_protection.timezone.now", return_value=now + datetime.timedelta(hours=1)):
            self.assertEqual(self.submit(self.payload()).status_code, 302)
