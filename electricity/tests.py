import datetime
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from django.contrib.auth.models import User

from .forms import ElectricalServiceForm, OnCallBookingForm, ServiceBookingForm, Step2Form
from .models import ElectricianBooking, ElectricalService, OnCallBooking, ProviderProfile, ProviderShift, ServiceBooking, ServicePricing
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
                "bullet_points_en": "",
                "bullet_points_ar": "",
                "bullet_points_sv": "",
                "price": "1200",
                "duration_minutes": "60",
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
        self.assertNotIn("short_description_en", form.fields)
        item = form.save()
        self.assertEqual(item.short_description, "")

    def test_electrical_service_form_includes_booking_fields(self):
        form = ElectricalServiceForm()

        self.assertIn("price", form.fields)
        self.assertIn("duration_minutes", form.fields)

    def test_step_2_form_accepts_free_form_property_size(self):
        form = Step2Form(
            data={
                "property_type": "apartment",
                "property_size": "87 m2",
                "year_built": "2014",
                "property_type_other": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["property_size"], "87 m2")


class ElectricianBookingReceiptTests(TestCase):
    def test_confirm_booking_step_creates_booking_without_server_error(self):
        session = self.client.session
        session["electricity_electrician_booking"] = {
            "hours": "2",
            "work_description": "Replace faulty breaker.",
            "service_type": "commercial",
            "street_address": "Sveavagen 10",
            "zip_code": "111 57",
            "city": "Stockholm",
            "customer_type": ElectricianBooking.CustomerType.BUSINESS,
            "company_name": "ACME AB",
            "organization_number": "556677-8899",
            "phone": "0701234567",
            "email": "ops@example.com",
            "access_notes": "Gate code 1234",
            "parking_info": "Visitor parking",
            "additional_notes": "Call before arrival.",
            "preferred_date": (timezone.localdate() + datetime.timedelta(days=1)).isoformat(),
            "arrival_window": "Morning (08:00 AM - 12:00 PM)",
            "pricing_ack": True,
        }
        session.save()

        response = self.client.post(
            reverse("electricity:electrician_booking_step", args=[8]),
            {
                "confirm_info": "yes",
                "accept_terms": "yes",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("electricity:electrician_booking_thank_you"))
        booking = ElectricianBooking.objects.get()
        self.assertEqual(booking.full_name, "ACME AB")
        self.assertEqual(booking.phone, "0701234567")
        self.assertIn("Organization number: 556677-8899", booking.additional_notes)

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

        response = self.client.get(reverse("electricity:electrician_booking_thank_you"), secure=True)

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
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please choose a date from today onward.")


class ContactFormTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        CONTACT_TO_EMAIL="info@rwmel.se",
        DEFAULT_FROM_EMAIL="support@rwmel.se",
    )
    def test_contact_form_sends_to_info_address(self):
        response = self.client.post(
            reverse("electricity:contact"),
            {
                "full_name": "Test User",
                "email": "customer@example.com",
                "phone": "0701234567",
                "address": "Main Street 1",
                "request_type": "Residential",
                "inquiry_type": "tech_support",
                "message": "Need help with a breaker issue.",
                "consent": "on",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you! We have received your request.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["info@rwmel.se"])
        self.assertEqual(mail.outbox[0].from_email, "support@rwmel.se")
        self.assertEqual(mail.outbox[0].reply_to, ["customer@example.com"])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        CONTACT_TO_EMAIL="info@rwmel.se",
        DEFAULT_FROM_EMAIL="services@rwmel.se",
        EMAIL_HOST_USER="support@rwmel.se",
    )
    def test_contact_form_defaults_inquiry_type_and_uses_smtp_user_as_sender(self):
        response = self.client.post(
            reverse("electricity:contact"),
            {
                "full_name": "Test User",
                "email": "customer@example.com",
                "phone": "0701234567",
                "address": "Main Street 1",
                "request_type": "Residential",
                "message": "Need help with a breaker issue.",
                "consent": "on",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you! We have received your request.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["info@rwmel.se"])
        self.assertEqual(mail.outbox[0].from_email, "support@rwmel.se")


class SupportFormTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="services@rwmel.se",
        EMAIL_HOST_USER="support@rwmel.se",
    )
    def test_support_form_sends_to_support_address(self):
        response = self.client.post(
            reverse("electricity:support"),
            {
                "full_name": "Support User",
                "email": "customer@example.com",
                "phone": "0701234567",
                "request_type": "Urgent support",
                "customer_type": "Business",
                "project_address": "Main Street 1",
                "message": "Need urgent help with an outage.",
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ST-")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["support@rwmel.se"])
        self.assertEqual(mail.outbox[0].from_email, "support@rwmel.se")
        self.assertEqual(mail.outbox[0].reply_to, ["customer@example.com"])


class BookingEmailTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        BOOKING_FROM_EMAIL="services@rwmel.se",
        DEFAULT_FROM_EMAIL="support@rwmel.se",
    )
    def test_booking_confirmation_helper_uses_booking_from_email(self):
        from .views import _send_custom_booking_confirmation_email

        _send_custom_booking_confirmation_email(
            to_email="customer@example.com",
            customer_name="Customer",
            booking_reference="REF-000001",
            booking_type_label="Service Booking",
            team_name="RWM EL",
            preferred_date=datetime.date(2026, 5, 1),
            preferred_time="09:00",
            summary_lines=["Estimated total: SEK 1200.00"],
            next_steps=["We will confirm your booking shortly."],
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "services@rwmel.se")
        self.assertEqual(mail.outbox[0].to, ["customer@example.com"])
        self.assertIn("Summary:", mail.outbox[0].body)
        self.assertIn("Estimated total: SEK 1200.00", mail.outbox[0].body)
        self.assertIn("Next steps:", mail.outbox[0].body)

    @override_settings(BOOKING_FROM_EMAIL="services@rwmel.se")
    def test_consultation_booking_triggers_customer_confirmation_email(self):
        session = self.client.session
        session["electricity_zip_checks"] = {"consultation": "11144"}
        session["electricity_booking"] = {
            "consultation_type": "inspection",
            "property_type": "apartment",
            "property_size": "80",
            "urgent": True,
            "full_name": "Consult Customer",
            "contact_type": "private",
            "personal_id": "19900101-1234",
            "email": "consult@example.com",
            "phone": "0701111111",
            "preferred_date": datetime.date(2026, 5, 1).isoformat(),
        }
        session.save()

        with patch("electricity.views._send_custom_booking_confirmation_email") as mocked:
            response = self.client.post(
                reverse("electricity:booking_step_7"),
                {"preferred_date": "2026-05-01", "preferred_time": "09:00"},
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs["to_email"], "consult@example.com")
        self.assertEqual(mocked.call_args.kwargs["booking_type_label"], "Consultation Booking")
        self.assertIn("Consultation type:", mocked.call_args.kwargs["summary_lines"][0])

    @override_settings(BOOKING_FROM_EMAIL="services@rwmel.se")
    def test_electrician_booking_triggers_customer_confirmation_email(self):
        session = self.client.session
        session["electricity_electrician_booking"] = {
            "hours": "2",
            "work_description": "Replace faulty breaker.",
            "service_type": "commercial",
            "street_address": "Sveavagen 10",
            "zip_code": "111 57",
            "city": "Stockholm",
            "customer_type": ElectricianBooking.CustomerType.BUSINESS,
            "company_name": "ACME AB",
            "organization_number": "556677-8899",
            "phone": "0701234567",
            "email": "electrician@example.com",
            "additional_notes": "Call before arrival.",
            "preferred_date": (timezone.localdate() + datetime.timedelta(days=1)).isoformat(),
            "arrival_window": "Morning (08:00 AM - 12:00 PM)",
            "pricing_ack": True,
        }
        session.save()

        with patch("electricity.views._send_custom_booking_confirmation_email") as mocked:
            response = self.client.post(
                reverse("electricity:electrician_booking_step", args=[8]),
                {"confirm_info": "yes", "accept_terms": "yes"},
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs["to_email"], "electrician@example.com")
        self.assertEqual(mocked.call_args.kwargs["booking_type_label"], "Electrician Booking")
        self.assertIn("Estimated total:", mocked.call_args.kwargs["summary_lines"][3])

    @override_settings(BOOKING_FROM_EMAIL="services@rwmel.se")
    def test_on_call_booking_triggers_customer_confirmation_email(self):
        session = self.client.session
        session["electricity_zip_checks"] = {"on_call": "11144"}
        session["electricity_on_call_booking"] = {
            "entity_type": "business",
            "organization_name": "ACME AB",
            "organization_number": "556677-8899",
            "contact_person": "Ops Team",
            "phone": "0701234567",
            "email": "oncall@example.com",
            "company_address": "Main Street 1",
            "zip_code": "11144",
            "city": "Stockholm",
            "coverage_times": ["evenings"],
            "response_speed": "standard",
            "coverage_scope": ["power_outages"],
            "property_type": "commercial",
            "assets_count": "2",
            "primary_region": "Stockholm",
        }
        session.save()

        with patch("electricity.views._send_custom_booking_confirmation_email") as mocked:
            response = self.client.post(
                reverse("electricity:on_call_booking_step", args=[4]),
                {"recurring_issues": "Frequent outages", "emergency_hours": "2"},
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs["to_email"], "oncall@example.com")
        self.assertEqual(mocked.call_args.kwargs["booking_type_label"], "On-Call Booking")
        self.assertIn("Coverage scope:", mocked.call_args.kwargs["summary_lines"][2])

    @override_settings(BOOKING_FROM_EMAIL="services@rwmel.se")
    def test_service_booking_triggers_customer_confirmation_email(self):
        service = ElectricalService.objects.create(
            title="Panel Upgrade",
            short_description="Upgrade panel",
            price="1200.00",
            duration_minutes=60,
            is_active=True,
        )
        provider_user = User.objects.create_user(username="provider1", password="x")
        provider = ProviderProfile.objects.create(
            user=provider_user,
            display_name="Provider One",
            zip_code="11144",
            is_active=True,
        )
        preferred_date = timezone.localdate() + datetime.timedelta(days=1)
        ProviderShift.objects.create(
            provider=provider,
            weekday=preferred_date.weekday(),
            start_time=datetime.time(8, 0),
            end_time=datetime.time(17, 0),
        )

        session = self.client.session
        session["electricity_zip_checks"] = {"service": "11144"}
        session["electricity_service_booking"] = {
            "account_type": ServiceBooking.AccountType.PRIVATE,
            "full_name": "Service Customer",
            "email": "service@example.com",
            "phone": "0709999999",
            "street_address": "Main Street 1",
            "city": "Stockholm",
            "region": "Stockholm",
            "country": "Sweden",
            "property_type": "apartment",
            "year_built": "2000",
            "property_size": "90",
            "services": [str(service.id)],
            "work_description": "Upgrade panel",
            "pricing_type": ServiceBooking.PricingType.FIXED,
            "preferred_date": preferred_date.isoformat(),
            "preferred_time_slot": "09:00",
            "billing_type": "private",
            "personal_id": "19900101-1234",
        }
        session.save()

        with patch("electricity.views._send_custom_booking_confirmation_email") as mocked:
            response = self.client.post(
                reverse("electricity:service_booking_step", args=[11]),
                {},
                secure=True,
            )

        self.assertEqual(response.status_code, 302)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs["to_email"], "service@example.com")
        self.assertEqual(mocked.call_args.kwargs["booking_type_label"], "Service Booking")
        self.assertIn("Selected services:", mocked.call_args.kwargs["summary_lines"][0])
