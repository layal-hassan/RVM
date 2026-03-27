import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ElectricalServiceForm, OnCallBookingForm, ServiceBookingForm
from .models import ElectricianBooking, ElectricalService, OnCallBooking, ServiceBooking, ServicePricing
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

    def test_electrical_service_form_allows_empty_short_description(self):
        form = ElectricalServiceForm(
            data={
                "title_en": "Panel Upgrade",
                "title_ar": "Panel Arabic",
                "title_sv": "Paneluppgradering",
                "short_description_en": "",
                "short_description_ar": "",
                "short_description_sv": "",
                "bullet_points_en": "",
                "bullet_points_ar": "",
                "bullet_points_sv": "",
                "service_fee": "0",
                "base_fee": "0",
                "hourly_rate": "0",
                "night_rate": "0",
                "transport_fee": "0",
                "rot_percent": "30",
                "currency": "SEK",
                "is_active": "on",
                "order": "0",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual(item.short_description, "")


class ElectricianBookingReceiptTests(TestCase):
    def test_thank_you_uses_saved_booking_details_instead_of_cleared_session_defaults(self):
        booking = ElectricianBooking.objects.create(
            customer_type=ElectricianBooking.CustomerType.BUSINESS,
            full_name="ACME AB",
            email="ops@example.com",
            phone="556677-8899",
            street_address="Sveavagen 10",
            city="Stockholm",
            zip_code="111 57",
            property_type="commercial",
            work_description="Replace faulty breaker and inspect panel.",
            hours=3,
            hourly_rate_snapshot="688.00",
            transport_fee_snapshot="495.00",
            estimated_total="2559.00",
            preferred_date=datetime.date(2026, 10, 5),
            arrival_window="Morning (08:00 AM - 12:00 PM)",
            currency="SEK",
        )
        session = self.client.session
        session["electrician_booking_id"] = booking.id
        session["electrician_booking_reference"] = f"RWM-{booking.id:06d}"
        session.save()

        response = self.client.get(reverse("electricity:electrician_booking_thank_you"))

        self.assertContains(response, "Commercial Maintenance")
        self.assertContains(response, "Business / Organization")
        self.assertContains(response, "Sveavagen 10, 111 57 Stockholm")
        self.assertContains(response, "Replace faulty breaker and inspect panel.")
        self.assertContains(response, "SEK 495.00")
        self.assertContains(response, "SEK 2559.00")
        self.assertNotContains(response, "1248 Oakwood Ave")
        self.assertNotContains(response, "Residential Property")

    def test_pricing_breakdown_adds_transport_fee_to_total(self):
        pricing = ServicePricing.objects.create(
            name="Default",
            transport_fee="495.00",
            hourly_rate_electrician="100.00",
            currency="SEK",
            is_active=True,
        )

        from .views import _electrician_pricing_breakdown

        breakdown = _electrician_pricing_breakdown({"hours": "3"})

        self.assertEqual(breakdown["minimum_callout"], 100.0)
        self.assertEqual(breakdown["additional_total"], 200.0)
        self.assertEqual(breakdown["transport_fee"], 495.0)
        self.assertEqual(breakdown["total"], 795.0)

    def test_step_6_rejects_past_dates(self):
        session = self.client.session
        session["electricity_electrician_booking"] = {}
        session.save()

        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        response = self.client.post(
            reverse("electricity:electrician_booking_step", args=[6]),
            {
                "preferred_date": yesterday,
                "arrival_window": "Morning (08:00 AM - 12:00 PM)",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please choose a date from today onward.")
