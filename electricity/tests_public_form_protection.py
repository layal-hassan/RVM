import datetime
from unittest.mock import Mock, patch

from django.core import mail
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from .form_protection import client_ip, public_submission_retry_after, reject_public_submission
from .middleware import PublicFormSpamProtectionMiddleware
from .models import SupportTicket, PublicFormSubmissionBucket, OnCallBooking, QuoteRequest


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SECURE_SSL_REDIRECT=False, FORM_IP_LIMIT=5, FORM_IP_DAILY_LIMIT=20)
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
        # Only valid submissions count, across different forms sharing an IP.
        for index in range(5):
            route = "support" if index % 2 == 0 else "contact"
            response = self.client.post(reverse(f"electricity:{route}"), self.payload(index, consent="yes"))
            self.assertNotEqual(response.status_code, 429)
        response = self.client.post(reverse("electricity:for_brf"), self.payload(9, brf_name="BRF", address="Test address"))
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
                with patch("electricity.form_protection.public_submission_retry_after", return_value=0) as guard:
                    middleware.process_view(request, Mock(), (), {"step": current_step})
                    if current_step == 1:
                        guard.assert_not_called()
                    else:
                        guard.assert_not_called()
                        reject_public_submission(request)
                        self.assertEqual(guard.call_args.args[2]["email"], "actual@example.com")

    def test_get_and_staff_dashboard_posts_are_not_limited(self):
        middleware = PublicFormSpamProtectionMiddleware(lambda request: HttpResponse())
        for method, name in (("get", "support"), ("post", "dashboard_invoices")):
            path = reverse(f"electricity:{name}")
            request = getattr(RequestFactory(), method)(path)
            request.resolver_match = resolve(path)
            with patch("electricity.form_protection.public_submission_retry_after") as guard:
                self.assertIsNone(middleware.process_view(request, Mock(), (), {}))
                guard.assert_not_called()


    def test_invalid_submissions_do_not_consume_capacity(self):
        for route in ("support", "contact", "for_brf", "feedback", "careers", "signup"):
            for _ in range(6):
                response = self.client.post(reverse(f"electricity:{route}"), {"email": "customer@example.com"})
                self.assertNotEqual(response.status_code, 429)
        self.assertFalse(PublicFormSubmissionBucket.objects.exists())
        self.assertEqual(self.client.post(reverse("electricity:support"), self.payload()).status_code, 200)
        self.assertEqual(SupportTicket.objects.count(), 1)

    def test_rejected_duplicates_do_not_consume_other_limits(self):
        request = RequestFactory().post("/support/")
        self.assertEqual(public_submission_retry_after(request, "support", self.payload()), 0)
        for _ in range(10):
            self.assertGreater(public_submission_retry_after(request, "support", self.payload()), 0)
        self.assertEqual(public_submission_retry_after(request, "support", self.payload(1)), 0)

    def test_contact_limits_do_not_block_different_forms(self):
        request = RequestFactory().post("/support/")
        for index in range(3):
            self.assertEqual(public_submission_retry_after(request, "support", self.payload(index, email="same@example.com")), 0)
        self.assertEqual(public_submission_retry_after(request, "contact", self.payload(8, email="same@example.com")), 0)

    def test_ajax_limit_returns_json_and_keeps_entered_data(self):
        request = RequestFactory().post("/request-flow/submit/", self.payload())
        request.public_submission_context = ("request_flow_submit", self.payload())
        self.assertIsNone(reject_public_submission(request))
        response = reject_public_submission(request)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn(b'"ok": false', response.content)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(request.POST["email"], self.payload()["email"])

    def test_rate_limit_page_shows_wait_and_return_link(self):
        self.client.post(reverse("electricity:support"), self.payload())
        response = self.client.post(reverse("electricity:support"), self.payload())
        self.assertContains(response, "Back to form", status_code=429)
        self.assertContains(response, "minute(s)", status_code=429)
        self.assertContains(response, "Call us", status_code=429)


    def test_on_call_complete_flow_allows_validation_retries_and_submits_once(self):
        session = self.client.session
        session["electricity_zip_checks"] = {"on_call": "11144"}
        session.save()
        def post(step, data):
            return self.client.post(reverse("electricity:on_call_booking_step", args=[step]), data)
        self.assertEqual(post(1, {"coverage_times": ["evenings"], "coverage_scope": ["power_outages"], "response_speed": "standard"}).status_code, 302)
        self.assertEqual(post(2, {
            "entity_type": "business", "organization_name": "ACME AB", "organization_number": "556677-8899",
            "contact_person": "Customer", "email": "customer@example.com", "phone": "0701234567",
            "company_address": "Main Street 1", "zip_code": "11144", "city": "Stockholm",
        }).status_code, 302)
        response = post(3, {"property_type": "commercial", "assets_count": "invalid", "primary_region": "Stockholm"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["errors"])
        # Invalid step-three data cannot crash a manually opened final-step URL.
        self.assertRedirects(post(4, {"emergency_hours": "1", "recurring_issues": "Outages"}), reverse("electricity:on_call_booking_step", args=[3]), fetch_redirect_response=False)
        self.assertEqual(post(3, {"property_type": "commercial", "assets_count": "2", "primary_region": "Stockholm"}).status_code, 302)
        for _ in range(6):
            response = post(4, {"emergency_hours": "bad", "recurring_issues": ""})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["errors"])
        self.assertFalse(PublicFormSubmissionBucket.objects.exists())
        response = post(4, {"emergency_hours": "2", "recurring_issues": "Recurring outages"})
        self.assertEqual(response.status_code, 302)
        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, "Submission confirmed")
        self.assertEqual(OnCallBooking.objects.count(), 1)
        # A repeated POST after the wizard session is cleared starts no second booking.
        self.assertEqual(post(4, {"emergency_hours": "2", "recurring_issues": "Recurring outages"}).status_code, 302)
        self.assertEqual(OnCallBooking.objects.count(), 1)

    def test_missing_on_call_session_redirects_without_using_limits(self):
        session = self.client.session
        session["electricity_zip_checks"] = {"on_call": "11144"}
        session.save()
        response = self.client.post(reverse("electricity:on_call_booking_step", args=[4]), {"emergency_hours": "1", "recurring_issues": "Outages"})
        self.assertRedirects(response, reverse("electricity:on_call_booking_step", args=[1]), fetch_redirect_response=False)
        self.assertFalse(OnCallBooking.objects.exists())
        self.assertFalse(PublicFormSubmissionBucket.objects.exists())

    def test_quote_final_step_missing_contact_redirects_instead_of_crashing(self):
        session = self.client.session
        session["electricity_quote_request"] = {"service_title": "Inspection", "customer_type": "private", "project_details": "Inspection", "materials": "unsure"}
        session.save()
        response = self.client.post(reverse("electricity:quote_request_step", args=[3]), {"confirm": "yes", "terms": "yes"})
        self.assertRedirects(response, reverse("electricity:quote_request_step", args=[2]), fetch_redirect_response=False)
        self.assertFalse(QuoteRequest.objects.exists())
        self.assertFalse(PublicFormSubmissionBucket.objects.exists())
