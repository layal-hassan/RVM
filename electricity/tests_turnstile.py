import json
from unittest.mock import Mock, patch
from urllib.error import URLError
from urllib.parse import parse_qs

from django.core import mail
from django.template import Context, Template
from django.template.loader import get_template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse

from .form_protection import reject_public_submission
from .middleware import PublicFormSpamProtectionMiddleware
from .models import PublicFormSubmissionBucket, SupportTicket
from .turnstile import verify_submission


CONFIG = dict(TURNSTILE_ENABLED=True, TURNSTILE_SITE_KEY="public-site-key",
              TURNSTILE_SECRET_KEY="private-secret", SECURE_SSL_REDIRECT=False)


@override_settings(**CONFIG)
class TurnstileVerificationTests(TestCase):
    def request(self, token="valid-token"):
        return RequestFactory().post("/support/", {"cf-turnstile-response": token})

    def api_response(self, result):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(result).encode()
        return response

    @patch("electricity.turnstile.urlopen")
    def test_valid_token_checked_once_and_secret_only_sent_to_siteverify(self, api):
        api.return_value = self.api_response({"success": True, "hostname": "testserver"})
        request = self.request()
        self.assertIsNone(verify_submission(request, "support"))
        self.assertIsNone(verify_submission(request, "support"))
        api.assert_called_once()
        call = api.call_args
        self.assertEqual(parse_qs(call.args[0].data.decode()), {
            "secret": ["private-secret"], "response": ["valid-token"],
        })
        self.assertEqual(call.kwargs["timeout"], 10)

    @patch("electricity.turnstile.urlopen")
    def test_missing_and_oversized_tokens_never_call_cloudflare(self, api):
        for token in ("", " " * 3, "x" * 2049):
            self.assertEqual(verify_submission(self.request(token), "support").status_code, 400)
        api.assert_not_called()

    @patch("electricity.turnstile.urlopen")
    def test_invalid_expired_forged_or_wrong_hostname_tokens_fail_closed(self, api):
        for result in ({"success": False, "error-codes": ["timeout-or-duplicate"]},
                       {"success": True, "hostname": "attacker.example"},
                       {"success": "true", "hostname": "testserver"}, [], None):
            api.return_value = self.api_response(result)
            self.assertEqual(verify_submission(self.request(), "support").status_code, 400)

    @patch("electricity.turnstile.urlopen")
    def test_cloudflare_outage_and_malformed_response_fail_closed(self, api):
        for failure in (URLError("offline"), TimeoutError(), ValueError("Invalid JSON")):
            api.side_effect = failure
            response = verify_submission(self.request(), "request_flow_submit")
            self.assertEqual(response.status_code, 400)
            self.assertTrue(json.loads(response.content)["verification_required"])
            self.assertEqual(response["Cache-Control"], "no-store")

    @override_settings(TURNSTILE_ENABLED=False)
    @patch("electricity.turnstile.urlopen")
    def test_disabled_configuration_does_not_call_cloudflare_or_render_widget(self, api):
        self.assertIsNone(verify_submission(self.request(""), "support"))
        html = Template("{% load turnstile_tags %}{% turnstile_widget %}{% turnstile_scripts %}").render(Context())
        self.assertNotIn("data-turnstile", html)
        self.assertNotIn("turnstile.js", html)
        api.assert_not_called()

    def test_widget_exposes_public_key_only(self):
        html = Template("{% load turnstile_tags %}{% turnstile_widget %}").render(Context())
        self.assertIn("public-site-key", html)
        self.assertNotIn("private-secret", html)

    def test_all_public_submission_routes_use_the_shared_guard(self):
        middleware = PublicFormSpamProtectionMiddleware(lambda request: None)
        cases = [(name, {}) for name in middleware.direct_forms if name not in {"career_detail", "outside_area", "password_reset"}]
        cases += [("career_detail", {"slug": "electrician"}), ("outside_area", {"flow": "service", "zip_code": "12345"})]
        cases += [(name, {"step": step}) for name, (step, _) in middleware.final_steps.items()]
        cases += [("booking_step_7", {})]
        for name, kwargs in cases:
            with self.subTest(name=name):
                path = reverse("electricity:" + name, kwargs=kwargs)
                request = RequestFactory().post(path)
                request.session = {}
                request.resolver_match = resolve(path)
                middleware.process_view(request, Mock(), (), kwargs)
                with patch("electricity.form_protection.public_submission_retry_after") as limits:
                    self.assertEqual(reject_public_submission(request).status_code, 400)
                    limits.assert_not_called()


@override_settings(**CONFIG, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TurnstileSubmissionTests(TestCase):
    def payload(self, **extra):
        return {"full_name": "Test Customer", "email": "customer@example.com", "phone": "0701234567",
                "message": "Help with my electrical project", "request_type": "Support", **extra}

    def test_missing_token_does_not_save_send_or_consume_limits(self):
        response = self.client.post(reverse("electricity:support"), self.payload())
        self.assertContains(response, "security verification", status_code=400)
        self.assertFalse(SupportTicket.objects.exists())
        self.assertFalse(PublicFormSubmissionBucket.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    @patch("electricity.turnstile.urlopen")
    def test_verified_support_submission_saves_and_sends(self, api):
        api.return_value = TurnstileVerificationTests().api_response({"success": True, "hostname": "testserver"})
        response = self.client.post(reverse("electricity:support"), self.payload(**{"cf-turnstile-response": "token"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SupportTicket.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_is_also_protected(self):
        response = self.client.post(reverse("electricity:password_reset"), {"email": "customer@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_public_pages_render_and_do_not_leak_secret(self):
        for name in ("home", "support", "contact", "for_brf", "careers", "feedback", "signup", "password_reset"):
            with self.subTest(name=name):
                response = self.client.get(reverse("electricity:" + name))
                self.assertContains(response, "data-turnstile")
                self.assertContains(response, "turnstile.js")
                self.assertNotContains(response, "private-secret")

    def test_all_edited_templates_compile(self):
        for name in ("electricity/quote_request.html", "electricity/booking/base_booking.html",
                     "electricity/electrician_booking/step_8.html", "electricity/service_booking/step_6.html",
                     "electricity/on_call_booking/step_4.html", "electricity/career_detail.html",
                     "electricity/outside_area.html", "electricity/partials/request_flow_dialog.html"):
            get_template(name)
