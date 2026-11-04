from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    AdminNotification, CareerApplication, ConsultationBooking, ConsultationRequest,
    ContactInquiry, CustomerFeedback, ElectricianBooking, OnCallBooking,
    QuoteRequest, ServiceBooking, ServiceRequestOutsideArea, SupportTicket,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class NotificationNavigationTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username="notification-staff", is_staff=True)
        self.client.force_login(self.staff)

    def test_linked_records_open_correct_table_and_exact_row_regardless_of_message(self):
        cases = (
            ("consultation_request", ConsultationRequest, "dashboard_requests"),
            ("booking", ConsultationBooking, "dashboard_bookings"),
            ("service_booking", ServiceBooking, "dashboard_service_bookings"),
            ("electrician_booking", ElectricianBooking, "dashboard_electrician_bookings"),
            ("on_call_booking", OnCallBooking, "dashboard_on_call_bookings"),
            ("quote_request", QuoteRequest, "dashboard_quote_requests"),
            ("contact_inquiry", ContactInquiry, "dashboard_contact_inquiries"),
            ("feedback", CustomerFeedback, "dashboard_feedback"),
            ("career_application", CareerApplication, "dashboard_career_applications"),
            ("support_ticket", SupportTicket, "dashboard_support_tickets"),
            ("outside_area_request", ServiceRequestOutsideArea, "dashboard_outside_area_requests"),
        )
        for field, model, route in cases:
            with self.subTest(field=field):
                values = {"account_type": "private", "full_name": "Service Customer", "email": "service@example.com"} if model is ServiceBooking else {}
                record = model.objects.create(**values)
                note = AdminNotification.objects.create(**{field: record}, message="A service called electrician career quote")
                expected = f"{reverse('electricity:' + route)}#record-{record.pk}"
                self.assertEqual(note.get_target_url(), expected)
                response = self.client.get(reverse("electricity:" + route))
                self.assertContains(response, f'id="record-{record.pk}"')

    def test_same_customer_name_does_not_confuse_quick_quote_targets(self):
        first = ConsultationRequest.objects.create(full_name="Same Name")
        second = ConsultationRequest.objects.create(full_name="Same Name")
        notes = [AdminNotification.objects.create(consultation_request=record, message="New quick quote request from Same Name.") for record in (first, second)]
        payload = self.client.get(reverse("electricity:admin_notifications_feed")).json()
        urls = {item["id"]: item["url"] for item in payload["items"]}
        for note, record in zip(notes, (first, second)):
            self.assertEqual(urls[note.pk], f"{reverse('electricity:dashboard_requests')}#record-{record.pk}")
        response = self.client.get(reverse("electricity:dashboard"))
        self.assertContains(response, f'href="{notes[0].get_target_url()}"')

    def test_mark_read_only_marks_selected_notification(self):
        first = AdminNotification.objects.create(message="First")
        second = AdminNotification.objects.create(message="Second")
        response = self.client.post(reverse("electricity:admin_notifications_mark_read"), {"notification_id": first.pk}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"updated": True, "unread_count": 1})
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertFalse(second.is_read)

    def test_old_unlinked_messages_never_default_to_consultation_bookings(self):
        for message, route in (
            ("New quick quote request from Old Customer.", "dashboard_requests"),
            ("New contact inquiry from Old Customer.", "dashboard_contact_inquiries"),
            ("New customer feedback from Old Customer.", "dashboard_feedback"),
        ):
            self.assertEqual(AdminNotification(message=message).get_target_url(), reverse("electricity:" + route))

    def test_backfill_links_unique_historical_record_but_skips_ambiguous_names(self):
        unique = ContactInquiry.objects.create(full_name="Unique Customer")
        linked = AdminNotification.objects.create(message="New contact inquiry from Unique Customer.")
        for _ in range(2):
            ContactInquiry.objects.create(full_name="Duplicate Customer")
        ambiguous = AdminNotification.objects.create(message="New contact inquiry from Duplicate Customer.")
        migration = import_module("electricity.migrations.0063_notification_record_links")
        migration.link_historical_notifications(apps, SimpleNamespace(connection=connection))
        linked.refresh_from_db()
        ambiguous.refresh_from_db()
        self.assertEqual(linked.contact_inquiry_id, unique.pk)
        self.assertIsNone(ambiguous.contact_inquiry_id)

    def test_contact_inquiries_shows_older_records_and_message(self):
        inquiry = ContactInquiry.objects.create(full_name="Original Customer", message="Please inspect the fuse board.")
        for index in range(8):
            ContactInquiry.objects.create(full_name=f"Newer Customer {index}")
        response = self.client.get(reverse("electricity:dashboard_contact_inquiries"))
        self.assertContains(response, f'id="record-{inquiry.pk}"')
        self.assertContains(response, inquiry.message)
        self.assertContains(response, "dashboard-notifications.js")

    def test_customer_cannot_read_dashboard_notification_feed_or_contact_inquiries(self):
        customer = get_user_model().objects.create_user(username="regular-customer")
        self.client.force_login(customer)
        for route in ("admin_notifications_feed", "dashboard_contact_inquiries"):
            self.assertEqual(self.client.get(reverse("electricity:" + route)).status_code, 302)
