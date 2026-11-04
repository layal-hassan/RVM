from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from django.utils import translation

from . import views


class Session(dict):
    modified = False


class ElectricianCustomerPopupTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        categories = patch("electricity.templatetags.electricity_extras.ServiceCategoryPage.objects.filter")
        category_query = categories.start()
        category_query.return_value.prefetch_related.return_value.order_by.return_value = []
        self.addCleanup(categories.stop)
        self.language = translation.override("en")
        self.language.__enter__()
        self.addCleanup(self.language.__exit__, None, None, None)
        pricing = patch.object(views, "_electrician_pricing_breakdown", return_value={})
        pricing.start()
        self.addCleanup(pricing.stop)

    def request(self, step=2, post=None, data=None):
        path = reverse("electricity:electrician_booking_step", args=[step])
        request = self.factory.get(path) if post is None else self.factory.post(path, post)
        request.session = Session({views.ELECTRICIAN_BOOKING_SESSION_KEY: data or {}})
        return request, views.electrician_booking_step(request, step)

    def test_old_entry_opens_service_page(self):
        _, response = self.request(step=1)
        self.assertEqual(response.url, reverse("electricity:electrician_booking_step", args=[2]))

    def test_service_page_contains_popup_and_seven_steps(self):
        _, response = self.request()
        self.assertContains(response, "data-contact-dialog")
        self.assertContains(response, 'data-choice-name="customer_type"')
        self.assertContains(response, "consultation-start.js")
        self.assertContains(response, '<div class="eb-step ', count=7)
        self.assertContains(response, 'class="eb-step-badge">1</span>')
        self.assertNotContains(response, '<div>Customer type</div>')

    def test_both_customer_types_persist_with_service(self):
        for customer_type in ("private", "business"):
            with self.subTest(customer_type=customer_type):
                request, response = self.request(post={"customer_type": customer_type, "service_type": "lighting", "work_description": "Install kitchen lights"})
                self.assertEqual(response.url, reverse("electricity:electrician_booking_step", args=[3]))
                saved = request.session[views.ELECTRICIAN_BOOKING_SESSION_KEY]
                self.assertEqual(saved["customer_type"], customer_type)
                self.assertEqual(saved["service_type"], "lighting")

    def test_customer_type_is_required_on_server(self):
        for customer_type in (None, "other"):
            post = {"service_type": "lighting"}
            if customer_type:
                post["customer_type"] = customer_type
            _, response = self.request(post=post)
            self.assertContains(response, "Please choose Private or Business.")

    def test_legacy_popup_post_still_works(self):
        request, response = self.request(step=1, post={"customer_type": "business"})
        self.assertEqual(response.url, reverse("electricity:electrician_booking_step", args=[2]))
        self.assertEqual(request.session[views.ELECTRICIAN_BOOKING_SESSION_KEY]["customer_type"], "business")

    def test_returning_customer_keeps_choice_and_final_step_is_seven(self):
        _, response = self.request(data={"customer_type": "business", "service_type": "lighting"})
        self.assertContains(response, 'value="business" checked')
        self.assertContains(response, 'data-customer-business="Describe the project"')
        _, response = self.request(step=8, data={"customer_type": "business"})
        self.assertContains(response, 'class="eb-step-badge">7</span>')
        self.assertContains(response, 'width: 100%')

    def test_service_booking_starts_with_shared_popup_and_service_step(self):
        with patch.object(views, "_get_service_pricing_context", return_value={}):
            request = self.factory.get("/service-booking/step-1/")
            request.session = Session(electricity_zip_checks={"service": "11144"})
            response = views.service_booking_step(request, 1)
            self.assertContains(response, "data-customer-popup")
            self.assertContains(response, 'data-choice-name="customer_type"')
            self.assertContains(response, "What do you need help with?")
            for customer_type in ("private", "business"):
                request = self.factory.post("/service-booking/step-1/", {
                    "customer_type": customer_type, "service_type": "lighting", "work_description": "Install lights",
                })
                request.session = Session(electricity_zip_checks={"service": "11144"})
                response = views.service_booking_step(request, 1)
                self.assertEqual(response.url, reverse("electricity:service_booking_step", args=[2]))
                self.assertEqual(request.session[views.SERVICE_BOOKING_SESSION_KEY]["account_type"], customer_type)

    def test_on_call_private_opens_residential_booking(self):
        request = self.factory.post("/on-call-booking/step-1/", {"customer_type": "private"})
        request.session = Session(electricity_zip_checks={"on_call": "11144"})
        response = views.on_call_booking_step(request, 1)
        self.assertEqual(response.url, reverse("electricity:electrician_booking_step", args=[2]))
        self.assertEqual(request.session[views.ELECTRICIAN_BOOKING_SESSION_KEY]["customer_type"], "private")

    def test_on_call_business_continues_agreement(self):
        request = self.factory.post("/on-call-booking/step-1/", {
            "customer_type": "business", "coverage_times": ["evenings"],
            "response_speed": "standard", "coverage_scope": ["power_outages"],
        })
        request.session = Session(electricity_zip_checks={"on_call": "11144"})
        response = views.on_call_booking_step(request, 1)
        self.assertEqual(response.url, reverse("electricity:on_call_booking_step", args=[2]))
        self.assertEqual(request.session[views.ON_CALL_BOOKING_SESSION_KEY]["customer_type"], "business")

    def test_on_call_requires_customer_choice(self):
        with patch.object(views, "_get_active_pricing", return_value=None):
            request = self.factory.post("/on-call-booking/step-1/", {
                "coverage_times": ["evenings"], "response_speed": "standard", "coverage_scope": ["power_outages"],
            })
            request.session = Session(electricity_zip_checks={"on_call": "11144"})
            response = views.on_call_booking_step(request, 1)
            self.assertContains(response, "Please choose Private or Business.")
            self.assertContains(response, "data-submit-on-private")

    def test_consultation_and_quote_use_shared_popup(self):
        from django.template.loader import render_to_string
        from .forms import Step1Form
        consultation = render_to_string("electricity/booking/step_1.html", {"form": Step1Form()})
        self.assertIn('data-choice-name="contact_type"', consultation)
        quote = render_to_string("electricity/quote_request.html", {"step": 1, "data": {}})
        self.assertIn('data-choice-name="customer_type"', quote)
        self.assertNotIn("Who is requesting the quote?", quote)

    def test_landing_and_cart_can_open_popup_without_interrupting_browsing(self):
        from django.template.loader import render_to_string
        home = render_to_string("electricity/landing.html", {})
        self.assertIn('id="home-booking-dialog"', home)
        self.assertIn('id="quick-quote-customer-dialog"', home)
        self.assertIn("data-submit-on-choice", home)
        self.assertIn("data-popup-on-focus", home)
        self.assertIn("consultation-start.js", home)
        cart = render_to_string("electricity/partials/request_flow_dialog.html", {})
        self.assertIn('id="request-customer-dialog"', cart)
        self.assertIn('value="brf"', cart)
        self.assertIn("data-popup-manual", cart)

    def test_saved_business_draft_requires_popup_on_new_entry(self):
        _, response = self.request(data={"customer_type": "business", "service_type": "lighting"})
        self.assertContains(response, 'value="business" checked')
        self.assertNotContains(response, "data-popup-confirmed")

    def test_homepage_choice_skips_popup_only_on_immediate_redirect(self):
        request, response = self.request(step=1, post={"customer_type": "business"})
        self.assertEqual(response.status_code, 302)
        follow = self.factory.get(response.url)
        follow.session = request.session
        response = views.electrician_booking_step(follow, 2)
        self.assertContains(response, "data-popup-confirmed")
        self.assertNotIn(views.ELECTRICIAN_CUSTOMER_CONFIRMED_SESSION_KEY, follow.session)
        response = views.electrician_booking_step(follow, 2)
        self.assertNotContains(response, "data-popup-confirmed")

    def test_new_entry_link_clears_unused_confirmation(self):
        request = self.factory.get(reverse("electricity:electrician_booking_step", args=[1]))
        request.session = Session({
            views.ELECTRICIAN_BOOKING_SESSION_KEY: {"customer_type": "business"},
            views.ELECTRICIAN_CUSTOMER_CONFIRMED_SESSION_KEY: "business",
        })
        response = views.electrician_booking_step(request, 1)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(views.ELECTRICIAN_CUSTOMER_CONFIRMED_SESSION_KEY, request.session)

    def test_confirmation_for_a_different_type_does_not_skip_popup(self):
        request = self.factory.get(reverse("electricity:electrician_booking_step", args=[2]))
        request.session = Session({
            views.ELECTRICIAN_BOOKING_SESSION_KEY: {"customer_type": "business"},
            views.ELECTRICIAN_CUSTOMER_CONFIRMED_SESSION_KEY: "private",
        })
        response = views.electrician_booking_step(request, 2)
        self.assertNotContains(response, "data-popup-confirmed")

    def test_work_description_and_attachment_section_are_on_service_page(self):
        _, response = self.request(data={"customer_type": "business", "work_description": "Inspect the panel"})
        self.assertContains(response, 'name="work_description"', count=1)
        self.assertContains(response, "Inspect the panel")
        self.assertContains(response, "Add attachments (optional)")
        _, response = self.request(step=3, data={"customer_type": "business", "work_description": "Inspect the panel"})
        self.assertNotContains(response, 'name="work_description"')
        self.assertNotContains(response, "Add attachments (optional)")
        self.assertContains(response, 'name="hours"')

    def test_service_step_requires_a_description_and_preserves_it_on_errors(self):
        _, response = self.request(post={"customer_type": "private", "service_type": "lighting", "work_description": "   "})
        self.assertContains(response, "Please describe the work.")
        _, response = self.request(post={"customer_type": "private", "work_description": "Install lights"})
        self.assertContains(response, "Please select a service type.")
        self.assertContains(response, "Install lights")
        _, response = self.request(post={"customer_type": "private", "service_type": "lighting", "work_description": "x" * 501})
        self.assertContains(response, "500 characters or fewer")

    def test_time_selection_keeps_description_saved_on_previous_step(self):
        for customer_type in ("private", "business"):
            with self.subTest(customer_type=customer_type):
                request, response = self.request(post={
                    "customer_type": customer_type, "service_type": "lighting", "work_description": "  Install kitchen lights  ",
                })
                self.assertEqual(response.status_code, 302)
                data = request.session[views.ELECTRICIAN_BOOKING_SESSION_KEY]
                _, response = self.request(step=3, post={"hours": "2"}, data=data)
                self.assertEqual(response.url, reverse("electricity:electrician_booking_step", args=[4]))
                self.assertEqual(data["work_description"], "Install kitchen lights")
                self.assertEqual(data["hours"], "2")

    def test_old_draft_without_description_returns_to_service_page(self):
        for post in (None, {"hours": "2"}):
            _, response = self.request(step=3, post=post, data={"customer_type": "private", "service_type": "lighting"})
            self.assertEqual(response.url, reverse("electricity:electrician_booking_step", args=[2]))

    def test_customer_fields_render_inside_closed_dialog_before_javascript(self):
        from html.parser import HTMLParser
        from django.template.loader import render_to_string

        class DialogFields(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inside_dialog = False
                self.fields_in_dialog = []
                self.closed_initially = False

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "dialog":
                    self.inside_dialog = True
                    self.closed_initially = "open" not in attrs
                if tag == "input" and attrs.get("name") == "customer_type":
                    self.fields_in_dialog.append(self.inside_dialog)

            def handle_endtag(self, tag):
                if tag == "dialog":
                    self.inside_dialog = False

        html = render_to_string("electricity/partials/customer_type_popup.html", {"choice_name": "customer_type"})
        parser = DialogFields()
        parser.feed(html)
        self.assertTrue(parser.closed_initially)
        self.assertEqual(parser.fields_in_dialog, [True, True])
        self.assertGreater(html.index("<script"), html.index("</dialog>"))
        self.assertNotIn(" defer", html)

    def test_popup_loading_keeps_booking_page_scripts(self):
        _, response = self.request()
        self.assertContains(response, "electrician_booking.js")
        self.assertContains(response, "consultation-start.js", count=1)
        from django.template.loader import render_to_string
        from .forms import Step1Form
        consultation = render_to_string("electricity/booking/step_1.html", {"form": Step1Form()})
        self.assertEqual(consultation.count("consultation-start.js"), 1)
        service = render_to_string("electricity/service_booking/step_1.html", {"step": 1, "data": {}})
        self.assertEqual(service.count("electrician_booking.js"), 1)
        self.assertEqual(service.count("consultation-start.js"), 1)

    def test_back_from_time_step_resumes_the_chosen_customer_type(self):
        data = {"customer_type": "private", "service_type": "lighting", "work_description": "Install lights"}
        _, response = self.request(step=3, data=data)
        back_url = reverse("electricity:electrician_booking_step", args=[2]) + "?resume=1"
        self.assertContains(response, 'href="' + back_url + '"')
        request = self.factory.get(back_url)
        request.session = Session({views.ELECTRICIAN_BOOKING_SESSION_KEY: data})
        response = views.electrician_booking_step(request, 2)
        self.assertContains(response, "data-popup-confirmed")
        self.assertContains(response, 'value="private" checked')
        self.assertContains(response, "Install lights")

    def test_resume_without_a_choice_still_requires_the_popup(self):
        request = self.factory.get(reverse("electricity:electrician_booking_step", args=[2]) + "?resume=1")
        request.session = Session()
        response = views.electrician_booking_step(request, 2)
        self.assertNotContains(response, "data-popup-confirmed")

    def test_other_booking_back_links_resume_the_current_booking(self):
        from django.template.loader import render_to_string
        for template, url_name in (
            ("booking", "booking_step_1"),
            ("service_booking", "service_booking_step"),
            ("on_call_booking", "on_call_booking_step"),
        ):
            with self.subTest(template=template):
                html = render_to_string("electricity/" + template + "/step_2.html", {"data": {}, "step": 2})
                args = None if template == "booking" else [1]
                self.assertIn(reverse("electricity:" + url_name, args=args) + "?resume=1", html)
