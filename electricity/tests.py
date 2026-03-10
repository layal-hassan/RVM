from django.test import TestCase

from .forms import OnCallBookingForm, ServiceBookingForm
from .models import ElectricalService, OnCallBooking, ServiceBooking
from .templatetags.electricity_extras import _service_title_map, display_value, file_display_name


class DisplayValueTests(TestCase):
    def setUp(self):
        _service_title_map.cache_clear()

    def test_display_value_humanizes_list_fields(self):
        booking = OnCallBooking(
            coverage_scope=["power_outages", "critical_systems"],
            coverage_times=["evenings", "nights"],
        )

        self.assertEqual(
            display_value(booking, "coverage_scope"),
            "Power outages, Critical systems",
        )
        self.assertEqual(
            display_value(booking, "coverage_times"),
            "Evenings, Nights",
        )

    def test_display_value_resolves_service_titles(self):
        first = ElectricalService.objects.create(
            title="Panel Upgrade",
            short_description="Upgrade panel",
        )
        second = ElectricalService.objects.create(
            title="EV Charger",
            short_description="Install charger",
        )
        booking = ServiceBooking(
            account_type=ServiceBooking.AccountType.PRIVATE,
            full_name="Test User",
            email="test@example.com",
            country="Sweden",
            pricing_type=ServiceBooking.PricingType.FIXED,
            status=ServiceBooking.Status.PENDING,
            services=[str(first.id), str(second.id)],
        )

        self.assertEqual(
            display_value(booking, "services"),
            "Panel Upgrade, EV Charger",
        )

    def test_file_display_name_prefers_original_name(self):
        class AttachmentStub:
            original_name = "report.pdf"

        self.assertEqual(file_display_name(AttachmentStub()), "report.pdf")


class HumanizedJSONModelFormTests(TestCase):
    def setUp(self):
        _service_title_map.cache_clear()

    def test_on_call_form_formats_json_initial_as_human_readable_lines(self):
        booking = OnCallBooking(
            coverage_scope=["power_outages", "critical_systems"],
            coverage_times=["evenings", "nights"],
        )

        form = OnCallBookingForm(instance=booking)

        self.assertEqual(
            form.initial["coverage_scope"],
            "Power outages\nCritical systems",
        )
        self.assertEqual(
            form.initial["coverage_times"],
            "Evenings\nNights",
        )

    def test_service_booking_form_parses_service_titles_to_ids(self):
        service = ElectricalService.objects.create(
            title="Panel Upgrade",
            short_description="Upgrade panel",
        )

        form = ServiceBookingForm(
            data={
                "account_type": ServiceBooking.AccountType.PRIVATE,
                "full_name": "Test User",
                "email": "test@example.com",
                "country": "Sweden",
                "pricing_type": ServiceBooking.PricingType.FIXED,
                "hourly_hours": 1,
                "hourly_rate_snapshot": "0",
                "fixed_services_total": "0",
                "duration_minutes": 0,
                "labor_rate": "0",
                "transport_fee": "0",
                "base_fee": "0",
                "service_fee_total": "0",
                "night_rate": "0",
                "currency": "SEK",
                "estimated_total": "0",
                "status": ServiceBooking.Status.PENDING,
                "services": "Panel Upgrade",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["services"], [str(service.id)])
