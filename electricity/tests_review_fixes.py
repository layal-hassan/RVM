from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .invoicing import _invoice_category_totals, create_credit_invoice, send_invoice_email
from .models import AutomatedEmailTemplate, CustomerProfile, Invoice, InvoiceLine, ServiceBooking
from .views import _send_custom_booking_confirmation_email


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CalendarPrivacyTests(TestCase):
    def setUp(self):
        self.booking = ServiceBooking.objects.create(account_type="private", full_name="Private Customer", email="private@example.com")
        self.url = reverse("electricity:service_booking_calendar", args=[self.booking.pk])

    def test_anonymous_and_unrelated_customer_cannot_download_calendar(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(get_user_model().objects.create_user(username="other-customer"))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_booking_owner_session_can_download_only_its_booking(self):
        session = self.client.session
        session["service_booking_pk"] = self.booking.pk
        session.save()
        response = self.client.get(self.url)
        self.assertContains(response, "private@example.com")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        other = ServiceBooking.objects.create(account_type="private", full_name="Other", email="other@example.com")
        self.assertEqual(self.client.get(reverse("electricity:service_booking_calendar", args=[other.pk])).status_code, 404)

    def test_staff_can_download_calendar(self):
        self.client.force_login(get_user_model().objects.create_user(username="calendar-staff", is_staff=True))
        self.assertEqual(self.client.get(self.url).status_code, 200)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InvoiceCorrectionTests(TestCase):
    def setUp(self):
        self.customer = CustomerProfile.objects.create(full_name="Invoice Customer", email="customer@example.com")

    def invoice(self, **options):
        invoice = Invoice.objects.create(customer=self.customer, recipient_email=self.customer.email, **options)
        InvoiceLine.objects.create(invoice=invoice, description="Labour", unit_price_ex_vat=Decimal("1000"), rot_eligible=True)
        invoice.recalculate()
        return invoice

    def test_full_credit_reverses_discounts_rot_vat_and_rounding(self):
        for invoice_discount in ("none", "fixed", "percent"):
            for row_discount in ("none", "fixed", "percent"):
                for rot in (False, True):
                    with self.subTest(invoice_discount=invoice_discount, row_discount=row_discount, rot=rot):
                        source = self.invoice(discount_type=invoice_discount, discount_value=Decimal("10"), rot_enabled=rot, rounding=Decimal("0.20"))
                        source.lines.update(discount_type=row_discount, discount_value=Decimal("15"))
                        InvoiceLine.objects.create(invoice=source, category="material", description="Materials", unit_price_ex_vat=Decimal("100"), vat_percent=Decimal("12"))
                        source.recalculate()
                        credit = create_credit_invoice(source)
                        for field in ("subtotal_ex_vat", "discount_total", "vat_total", "total_inc_vat", "rot_total", "invoice_total"):
                            self.assertEqual(getattr(credit, field), -getattr(source, field), field)
                        self.assertEqual(credit.amount_paid, 0)
                        self.assertEqual(credit.amount_due, -source.invoice_total)
                        original_totals = _invoice_category_totals(source)
                        for category, totals in _invoice_category_totals(credit).items():
                            for field, value in totals.items():
                                self.assertEqual(value, -original_totals[category][field])

    def test_full_credit_cannot_be_created_twice_or_for_another_credit(self):
        source = self.invoice()
        credit = create_credit_invoice(source)
        with self.assertRaisesMessage(ValueError, "already been credited"):
            create_credit_invoice(source)
        with self.assertRaisesMessage(ValueError, "cannot be credited again"):
            create_credit_invoice(credit)
        self.assertEqual(Invoice.objects.count(), 2)

    def test_credit_creation_rolls_back_if_copying_lines_fails(self):
        source = self.invoice()
        with patch("electricity.invoicing.InvoiceLine.objects.create", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                create_credit_invoice(source)
        source.refresh_from_db()
        self.assertEqual(source.status, Invoice.Status.DRAFT)
        self.assertEqual(Invoice.objects.count(), 1)

    @patch("electricity.invoicing.invoice_pdf_bytes", return_value=b"%PDF-test")
    def test_resending_paid_or_credited_invoice_preserves_financial_status(self, _pdf):
        for status in (Invoice.Status.PAID, Invoice.Status.CREDITED):
            with self.subTest(status=status):
                invoice = self.invoice(status=status, amount_paid=Decimal("1250"))
                send_invoice_email(invoice)
                invoice.refresh_from_db()
                self.assertEqual(invoice.status, status)
                self.assertEqual(invoice.amount_due, 0)
                self.assertIsNotNone(invoice.sent_at)

    @patch("electricity.invoicing.invoice_pdf_bytes", return_value=b"%PDF-test")
    def test_payment_recorded_while_sending_is_not_overwritten(self, _pdf):
        invoice = self.invoice()
        def accept_message(*args, **kwargs):
            Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.PAID, amount_paid=Decimal("1250"))
            return 1
        with patch("electricity.invoicing.EmailMultiAlternatives.send", side_effect=accept_message):
            send_invoice_email(invoice)
        self.assertEqual(invoice.status, Invoice.Status.PAID)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BookingConfirmationToggleTests(TestCase):
    def test_customer_toggle_is_respected_for_every_booking_workflow(self):
        cases = (("consultation", "Consultation Booking"), ("service", "Service Booking"), ("electrician", "Electrician Booking"), ("on_call", "On-Call Booking"))
        for enabled in (False, True):
            for workflow, label in cases:
                with self.subTest(workflow=workflow, enabled=enabled):
                    AutomatedEmailTemplate.objects.filter(workflow=workflow).update(customer_enabled=enabled)
                    mail.outbox.clear()
                    _send_custom_booking_confirmation_email(to_email="customer@example.com", customer_name="Customer", booking_reference="TEST", booking_type_label=label, team_name="RWM EL")
                    self.assertEqual(len(mail.outbox), int(enabled))
