import datetime
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ServiceBookingForm
from .models import AdminNotification, Invoice, ServiceBooking


class CompactServiceBookingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = override_settings(MEDIA_ROOT=self.temp.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.customer_mail = patch("electricity.views._send_custom_booking_confirmation_email")
        self.company_mail = patch("electricity.views._send_booking_company_notification_email")
        self.mail = self.customer_mail.start()
        self.company_mail.start()
        self.addCleanup(self.customer_mail.stop)
        self.addCleanup(self.company_mail.stop)
        session = self.client.session
        session["electricity_zip_checks"] = {"service": "11144"}
        session.save()
        self.date = (timezone.localdate() + datetime.timedelta(days=2)).isoformat()

    def url(self, step):
        return reverse("electricity:service_booking_step", args=[step])

    def post(self, step, data):
        return self.client.post(self.url(step), data, secure=True)

    def fill(self, customer="private", attachments=False):
        payloads = {
            1: {"customer_type": customer, "service_type": "lighting", "work_description": "Install six kitchen spotlights"},
            2: {"street_address": "Main Street 1", "zip_code": "11144", "city": "Stockholm", "location_details": "Floor 2"},
            3: {"preferred_date": self.date, "arrival_window": "Morning (08:00 AM - 12:00 PM)", "timing_notes": "Call before arrival"},
            4: {"full_name": "Booking Customer", "phone": "0701234567", "email": "customer@example.com", "use_rot": "no"},
            5: {"access_notes": "Door code 1234", "access_confirm": "yes"},
        }
        if customer == "business":
            payloads[4].update(company_name="ACME AB", organization_number="556677-8899", billing_email="billing@example.com", invoice_reference="Project A", purchase_order_number="PO-17")
            payloads[5].update(access_method="key_code", site_contact="Site Contact", site_contact_phone="0700000000", commercial_notes="Use the loading entrance", special_requirements="Bring a ladder")
            if attachments:
                payloads[5]["attachments"] = SimpleUploadedFile("site.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        for step, data in payloads.items():
            response = self.post(step, data)
            self.assertRedirects(response, self.url(step + 1), fetch_redirect_response=False)
        return payloads

    def test_private_flow_has_six_steps_and_no_hours(self):
        self.fill()
        for step in range(1, 7):
            response = self.client.get(self.url(step), secure=True)
            self.assertContains(response, '<div class="eb-step ', count=6)
            self.assertNotContains(response, 'name="hours"')
            self.assertNotContains(response, "Time estimate")
        response = self.post(6, {"accept_terms": "yes", "hours": "999"})
        self.assertRedirects(response, reverse("electricity:service_booking_thank_you"), fetch_redirect_response=False)
        booking = ServiceBooking.objects.get()
        self.assertEqual(booking.booking_version, 2)
        self.assertEqual(booking.account_type, "private")
        self.assertEqual(booking.service_type, "lighting")
        self.assertEqual(booking.work_description, "Install six kitchen spotlights")
        self.assertEqual(booking.booking_details["access_notes"], "Door code 1234")
        self.assertEqual(booking.booking_details["timing_notes"], "Call before arrival")
        self.assertEqual(booking.estimated_total, 0)
        self.assertEqual(booking.price_display, "To be confirmed")
        self.assertFalse(Invoice.objects.filter(service_booking=booking).exists())
        self.assertTrue(AdminNotification.objects.filter(service_booking=booking).exists())
        self.mail.assert_called_once()
        self.assertEqual(self.mail.call_args.kwargs["booking_type_label"], "Service Booking")
        self.assertNotIn("electricity_service_booking", self.client.session)
        receipt = self.client.get(response.url, secure=True)
        self.assertContains(receipt, "Install six kitchen spotlights")
        self.assertContains(receipt, "To be confirmed")
        self.post(6, {"accept_terms": "yes"})
        self.assertEqual(ServiceBooking.objects.count(), 1)

    def test_business_details_and_files_persist(self):
        self.fill("business", attachments=True)
        self.post(6, {"accept_terms": "yes"})
        booking = ServiceBooking.objects.get()
        self.assertEqual(booking.company_name, "ACME AB")
        self.assertEqual(booking.booking_details["billing_email"], "billing@example.com")
        self.assertEqual(booking.booking_details["purchase_order_number"], "PO-17")
        self.assertEqual(booking.booking_details["access_method"], "key_code")
        self.assertEqual(booking.booking_details["special_requirements"], "Bring a ladder")
        self.assertEqual(len(booking.attachment_links), 1)
        self.assertEqual(booking.uploads[0]["name"], "site.pdf")
        self.assertTrue(booking.uploads[0]["path"].startswith("electricity/service_booking/attachments/"))

    def test_steps_cannot_be_skipped(self):
        for step in range(2, 7):
            response = self.client.get(self.url(step), secure=True)
            self.assertRedirects(response, self.url(1), fetch_redirect_response=False)
        self.assertFalse(ServiceBooking.objects.exists())

    def test_invalid_fields_stay_on_their_own_step(self):
        response = self.post(1, {"customer_type": "other", "service_type": "other"})
        self.assertContains(response, "Please choose Private or Business.")
        self.post(1, {"customer_type": "private", "service_type": "lighting", "work_description": "Install lights"})
        response = self.post(2, {"street_address": "Main Street 1", "city": "Stockholm", "zip_code": "bad"})
        self.assertContains(response, "Enter a valid Swedish postal code.")
        self.post(2, {"street_address": "Main Street 1", "city": "Stockholm", "zip_code": "11144"})
        response = self.post(3, {"preferred_date": "2000-01-01", "arrival_window": "unknown"})
        self.assertContains(response, "Please choose a date from today onward.")
        self.assertContains(response, "Please select an arrival window.")

    def test_final_submission_requires_terms(self):
        self.fill()
        response = self.post(6, {})
        self.assertContains(response, "Please accept the Terms and Conditions.")
        self.assertFalse(ServiceBooking.objects.exists())
        self.mail.assert_not_called()

    def test_rot_eligibility_is_checked_and_saved(self):
        self.fill()
        response = self.post(4, {"full_name": "Customer", "phone": "0701234567", "email": "customer@example.com", "use_rot": "yes"})
        self.assertContains(response, "Please confirm the ROT eligibility statements.")
        response = self.post(4, {"full_name": "Customer", "phone": "0701234567", "email": "customer@example.com", "use_rot": "yes", "personal_id": "19900101-1234", "housing_type": "house", "property_designation": "Property 123", "rot_owner_confirm": "yes", "electronic_invoice_confirm": "yes"})
        self.assertEqual(response.status_code, 302)
        self.post(6, {"accept_terms": "yes"})
        booking = ServiceBooking.objects.get()
        self.assertTrue(booking.rot_deduction)
        self.assertTrue(booking.booking_details["rot_owner_confirm"])
        self.assertEqual(booking.booking_details["property_designation"], "Property 123")

    def test_back_link_resumes_the_popup_choice(self):
        self.fill()
        response = self.client.get(self.url(2), secure=True)
        back = self.url(1) + "?resume=1"
        self.assertContains(response, 'href="' + back + '"')
        response = self.client.get(back, secure=True)
        self.assertContains(response, "data-popup-confirmed")
        self.assertContains(response, "Install six kitchen spotlights")

    def test_legacy_urls_do_not_submit_old_flow(self):
        response = self.post(11, {})
        self.assertRedirects(response, self.url(6), fetch_redirect_response=False)
        self.assertFalse(ServiceBooking.objects.exists())

    def test_dashboard_shows_and_edits_new_fields_without_legacy_hours(self):
        self.fill("business", attachments=True)
        self.post(6, {"accept_terms": "yes"})
        booking = ServiceBooking.objects.get()
        admin = User.objects.create_user("staff", password="password", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("electricity:dashboard_service_bookings"), secure=True)
        self.assertContains(response, "Lighting installation")
        self.assertContains(response, "To be confirmed")
        edit = reverse("electricity:dashboard_service_bookings_edit", args=[booking.pk])
        response = self.client.get(edit + "?view=1", secure=True)
        self.assertContains(response, "billing@example.com")
        self.assertContains(response, "Bring a ladder")
        self.assertContains(response, "site.pdf")
        form = ServiceBookingForm(instance=booking)
        self.assertNotIn("hourly_hours", form.fields)
        self.assertNotIn("year_built", form.fields)
        data = {name: form.initial.get(name) or "" for name in form.fields}
        for name in ("rot_owner_confirm", "electronic_invoice_confirm", "access_confirm", "rot_deduction"):
            if not data.get(name): data.pop(name, None)
        data.update(billing_email="new-billing@example.com", access_notes="New code", estimated_total="1500.00", duration_minutes="0")
        response = self.client.post(edit, data, secure=True)
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.booking_details["billing_email"], "new-billing@example.com")
        self.assertEqual(booking.booking_details["access_notes"], "New code")
        self.assertEqual(booking.price_display, "1500.00 SEK")
        self.assertEqual(len(booking.uploads), 1)

    def test_legacy_record_stays_editable(self):
        booking = ServiceBooking.objects.create(account_type="private", full_name="Legacy Customer", email="legacy@example.com", services=["old-service"], hourly_hours=4, estimated_total="2000.00")
        form = ServiceBookingForm(instance=booking)
        self.assertEqual(booking.booking_version, 1)
        self.assertIn("hourly_hours", form.fields)
        self.assertIn("year_built", form.fields)
        self.assertEqual(booking.price_display, "2000.00 SEK")

    def test_staff_assigns_internal_duration_without_customer_hours(self):
        from .models import ProviderProfile, ProviderShift
        self.fill()
        self.post(6, {"accept_terms": "yes"})
        booking = ServiceBooking.objects.get()
        provider_user = User.objects.create_user("compact-provider", password="password")
        provider = ProviderProfile.objects.create(user=provider_user, display_name="Provider", zip_code="11144", is_active=True)
        date = datetime.date.fromisoformat(self.date)
        ProviderShift.objects.create(provider=provider, weekday=date.weekday(), start_time=datetime.time(8), end_time=datetime.time(17))
        admin = User.objects.create_user("assignment-staff", password="password", is_staff=True)
        self.client.force_login(admin)
        url = reverse("electricity:dashboard_service_bookings_assign", args=[booking.pk])
        response = self.client.post(url, {"assigned_provider": provider.pk}, secure=True)
        self.assertContains(response, "Set the internal scheduling duration.")
        response = self.client.post(url, {"assigned_provider": provider.pk, "start_at": self.date + "T09:00", "duration_minutes": "90"}, secure=True)
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.assigned_provider, provider)
        self.assertEqual(booking.duration_minutes, 90)
        self.assertEqual(booking.end_at - booking.start_at, datetime.timedelta(minutes=90))
        self.assertEqual(booking.status, ServiceBooking.Status.SCHEDULED)
        self.client.force_login(provider_user)
        response = self.client.get(reverse("electricity:provider_service_booking_detail", args=[booking.pk]), secure=True)
        self.assertContains(response, "Install six kitchen spotlights")
        self.assertContains(response, "Door code 1234")
        self.assertContains(response, "To be confirmed")

    def test_staff_cannot_assign_conflicting_time(self):
        from .models import ProviderProfile, ProviderShift
        self.fill()
        self.post(6, {"accept_terms": "yes"})
        booking = ServiceBooking.objects.get()
        provider_user = User.objects.create_user("busy-provider")
        provider = ProviderProfile.objects.create(user=provider_user, display_name="Busy Provider", zip_code="11144", is_active=True)
        date = datetime.date.fromisoformat(self.date)
        ProviderShift.objects.create(provider=provider, weekday=date.weekday(), start_time=datetime.time(8), end_time=datetime.time(17))
        start = timezone.make_aware(datetime.datetime.combine(date, datetime.time(9)))
        ServiceBooking.objects.create(account_type="private", full_name="Existing", email="existing@example.com", assigned_provider=provider, start_at=start, end_at=start + datetime.timedelta(hours=2))
        admin = User.objects.create_user("conflict-staff", is_staff=True)
        self.client.force_login(admin)
        response = self.client.post(reverse("electricity:dashboard_service_bookings_assign", args=[booking.pk]), {"assigned_provider": provider.pk, "start_at": self.date + "T09:30", "duration_minutes": "60"}, secure=True)
        self.assertContains(response, "Provider is not available for the full duration.")
        booking.refresh_from_db()
        self.assertIsNone(booking.assigned_provider)

    def test_submission_limits_apply_to_new_final_step(self):
        self.fill()
        self.post(6, {"accept_terms": "yes"})
        self.fill()
        response = self.post(6, {"accept_terms": "yes"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(ServiceBooking.objects.count(), 1)
        self.assertIn("electricity_service_booking", self.client.session)

    def test_invoice_uses_confirmed_fixed_price_and_business_billing_email(self):
        from .invoicing import create_invoice_for_booking
        self.fill("business")
        self.post(6, {"accept_terms": "yes"})
        booking = ServiceBooking.objects.get()
        self.assertIsNone(create_invoice_for_booking(booking))
        booking.estimated_total = "1500.00"
        booking.save()
        invoice = create_invoice_for_booking(booking)
        self.assertEqual(invoice.recipient_email, "billing@example.com")
        self.assertEqual(invoice.lines.count(), 1)
        self.assertEqual(invoice.lines.get().unit, "fixed price")
        self.assertEqual(invoice.total_inc_vat, 1500)

    def test_entry_starts_with_customer_popup_without_an_extra_zip_step(self):
        session = self.client.session
        session.pop("electricity_zip_checks", None)
        session.save()
        response = self.client.get(self.url(1), secure=True)
        self.assertContains(response, "data-customer-popup")
        self.assertContains(response, "What do you need help with?")
