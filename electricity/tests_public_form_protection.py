import datetime
from unittest.mock import Mock, patch

from django.core import mail
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from .form_protection import client_ip, public_submission_retry_after
from .middleware import PublicFormSpamProtectionMiddleware
from .models import SupportTicket


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PublicFormProtectionTests(TestCase):
    def payload(self, index=0, **overrides):
        data = {
            "full_name": "Test User", "email": f"customer{index}@example.com",
            "phone": f"07012345{index:02d}", "message": f"Help with project {index}",
            "request_type": "Support",
        }
        data.update(overrides)
        return data

    def test_fifty_identical_submissions_create_only_one_ticket_and_email(self):
        statuses = [self.client.post(reverse("electricity:support"), self.payload()).status_code for _ in range(50)]
        self.assertEqual(statuses.count(200), 1)
        self.assertEqual(statuses.count(429), 49)
        self.assertEqual(SupportTicket.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_ip_limit_is_shared_across_different_forms(self):
        # First five requests reach views (even if the particular form is invalid).
        for index in range(5):
            route = "support" if index % 2 == 0 else "contact"
            response = self.client.post(reverse(f"electricity:{route}"), self.payload(index))
            self.assertNotEqual(response.status_code, 429)
        response = self.client.post(reverse("electricity:for_brf"), self.payload(9))
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_changing_ip_or_phone_does_not_bypass_recipient_limit(self):
        for index in range(3):
            response = self.client.post(reverse("electricity:support"), self.payload(index, email="same@example.com"), REMOTE_ADDR=f"192.0.2.{index}")
            self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("electricity:support"), self.payload(8, email="SAME@example.com"), REMOTE_ADDR="192.0.2.99")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(SupportTicket.objects.count(), 3)

    def test_gmail_aliases_cannot_bypass_recipient_limit(self):
        for index, email in enumerate(("test.person@gmail.com", "testperson+one@gmail.com", "testperson@googlemail.com")):
            self.assertEqual(self.client.post(reverse("electricity:support"), self.payload(index, email=email)).status_code, 200)
        self.assertEqual(self.client.post(reverse("electricity:support"), self.payload(9, email="test.person+more@gmail.com")).status_code, 429)

    def test_phone_limit_survives_email_and_ip_changes(self):
        for index, phone in enumerate(("070 123 45 67", "+46 70 123 45 67", "0046701234567")):
            self.assertEqual(self.client.post(reverse("electricity:support"), self.payload(index, phone=phone), REMOTE_ADDR=f"192.0.2.{index}").status_code, 200)
        self.assertEqual(self.client.post(reverse("electricity:support"), self.payload(8, phone="0701234567"), REMOTE_ADDR="192.0.2.99").status_code, 429)

    def test_new_tokens_and_unrecognized_fields_do_not_bypass_duplicate_detection(self):
        data = self.payload()
        self.assertEqual(self.client.post(reverse("electricity:support"), data).status_code, 200)
        data.update(csrfmiddlewaretoken="new-mask", submission_token="new-token", random_field="new-value")
        self.assertEqual(self.client.post(reverse("electricity:support"), data).status_code, 429)

    def test_daily_limit_remains_after_hourly_limits_expire(self):
        base = timezone.now().replace(hour=1, minute=0, second=0, microsecond=0)
        request = RequestFactory().post("/support/")
        for index in range(5):
            with patch("electricity.form_protection.timezone.now", return_value=base + datetime.timedelta(hours=index)):
                self.assertEqual(public_submission_retry_after(request, "support", self.payload(index, email="same@example.com")), 0)
        with patch("electricity.form_protection.timezone.now", return_value=base + datetime.timedelta(hours=6)):
            self.assertGreater(public_submission_retry_after(request, "support", self.payload(9, email="same@example.com")), 0)
        with patch("electricity.form_protection.timezone.now", return_value=base + datetime.timedelta(days=1)):
            self.assertEqual(public_submission_retry_after(request, "support", self.payload(9, email="same@example.com")), 0)

    def test_ip_daily_limit_blocks_slow_rotating_contacts(self):
        base = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        request = RequestFactory().post("/support/")
        for index in range(20):
            with patch("electricity.form_protection.timezone.now", return_value=base + datetime.timedelta(minutes=11 * index)):
                self.assertEqual(public_submission_retry_after(request, "support", self.payload(index)), 0)
        with patch("electricity.form_protection.timezone.now", return_value=base + datetime.timedelta(hours=5)):
            self.assertGreater(public_submission_retry_after(request, "support", self.payload(50)), 0)

    def test_untrusted_forwarded_header_is_ignored(self):
        request = RequestFactory().post("/support/", REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR="198.51.100.1")
        self.assertEqual(client_ip(request), "192.0.2.1")

    @override_settings(FORM_TRUSTED_PROXY_NETWORKS=["127.0.0.1/32", "10.0.0.0/8"])
    def test_trusted_proxy_chain_uses_nearest_untrusted_address(self):
        request = RequestFactory().post("/support/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.99, 192.0.2.1, 10.0.0.2")
        self.assertEqual(client_ip(request), "192.0.2.1")
        request.META["HTTP_X_FORWARDED_FOR"] = "malformed"
        self.assertEqual(client_ip(request), "127.0.0.1")

    def test_only_final_booking_steps_are_guarded_and_use_session_contact(self):
        middleware = PublicFormSpamProtectionMiddleware(lambda request: HttpResponse())
        for route, step, session_key in (
            ("quote_request_step", 3, "electricity_quote_request"),
            ("electrician_booking_step", 8, "electricity_electrician_booking"),
            ("service_booking_step", 11, "electricity_service_booking"),
            ("on_call_booking_step", 4, "electricity_on_call_booking"),
        ):
            for current_step in (1, step):
                path = reverse(f"electricity:{route}", kwargs={"step": current_step})
                request = RequestFactory().post(path, {"email": "forged@example.com"})
                request.session = {session_key: {"email": "actual@example.com"}}
                request.resolver_match = resolve(path)
                with patch("electricity.middleware.public_submission_retry_after", return_value=0) as guard:
                    middleware.process_view(request, Mock(), (), {"step": current_step})
                    if current_step == 1:
                        guard.assert_not_called()
                    else:
                        self.assertEqual(guard.call_args.args[2]["email"], "actual@example.com")

    def test_get_and_staff_dashboard_posts_are_not_limited(self):
        middleware = PublicFormSpamProtectionMiddleware(lambda request: HttpResponse())
        for method, name in (("get", "support"), ("post", "dashboard_invoices")):
            path = reverse(f"electricity:{name}")
            request = getattr(RequestFactory(), method)(path)
            request.resolver_match = resolve(path)
            with patch("electricity.middleware.public_submission_retry_after") as guard:
                self.assertIsNone(middleware.process_view(request, Mock(), (), {}))
                guard.assert_not_called()
