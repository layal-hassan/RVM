from urllib.parse import urlencode

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ServiceCategoryPage, ServiceDetailPage
from .views import QUOTE_SESSION_KEY


@override_settings(SECURE_SSL_REDIRECT=False)
class ServicePageQuoteCTATests(TestCase):
    def setUp(self):
        self.category, _ = ServiceCategoryPage.objects.update_or_create(
            theme="electrical", defaults={
                "slug": "electrical-installations", "name": "Electrical Installations",
                "hero_title": "Electrical Installations",
                "hero_description": "Installation projects for your property.",
                "cta_title": "Need help?", "cta_secondary_label": "Get a Quote",
                "cta_secondary_url": reverse("electricity:booking_step_1"),
            },
        )
        self.detail = ServiceDetailPage.objects.create(
            parent_category=self.category, slug="quote-test-wiring", name="Wiring",
            hero_title="Wiring", cta_title="Need help?",
            cta_secondary_label="Get a Quote",
            cta_secondary_url=reverse("electricity:booking_step_1"),
        )

    def quote_url(self, page, source):
        return reverse("electricity:quote_request_step", args=[1]) + "?" + urlencode({
            "page": page.slug, "source": source,
        })

    def test_category_and_detail_buttons_open_quote_with_selected_service(self):
        for page, source, route in [
            (self.category, "category", "service_category_detail"),
            (self.detail, "detail", "service_detail"),
        ]:
            with self.subTest(source=source):
                response = self.client.get(reverse(f"electricity:{route}", args=[page.slug]))
                quote_url = self.quote_url(page, source)
                self.assertContains(response, f'href="{quote_url.replace("&", "&amp;")}"')
                response = self.client.get(quote_url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["data"]["service_title"], page.name)
                self.assertEqual(response.context["data"]["service_url"], reverse(f"electricity:{route}", args=[page.slug]))

    def test_post_keeps_selected_service_and_continues_to_contact_details(self):
        quote_url = self.quote_url(self.category, "category")
        self.client.get(quote_url)
        response = self.client.post(quote_url, {
            "customer_type": "private", "project_details": "Install kitchen lights",
            "materials": "unsure",
        })
        self.assertRedirects(response, reverse("electricity:quote_request_step", args=[2]))
        self.assertEqual(self.client.session[QUOTE_SESSION_KEY]["service_title"], self.category.name)

    def test_new_page_selection_replaces_previous_quote_details(self):
        session = self.client.session
        session[QUOTE_SESSION_KEY] = {"service_title": "Old service", "email": "old@example.com"}
        session.save()
        self.client.get(self.quote_url(self.category, "category"))
        self.assertNotIn("email", self.client.session[QUOTE_SESSION_KEY])
        response = self.client.get(reverse("electricity:quote_request_step", args=[1]), {"resume": "1"})
        self.assertEqual(response.context["data"]["service_title"], self.category.name)

    def test_custom_secondary_destination_is_preserved(self):
        self.category.cta_secondary_url = "/contact/"
        self.category.save()
        response = self.client.get(reverse("electricity:service_category_detail", args=[self.category.slug]))
        self.assertContains(response, 'href="/contact/">Get a Quote</a>')

    def test_inactive_pages_cannot_be_selected_for_a_quote(self):
        self.category.is_active = False
        self.category.save()
        response = self.client.get(self.quote_url(self.category, "category"))
        self.assertEqual(response.status_code, 404)
