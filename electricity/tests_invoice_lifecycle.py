from decimal import Decimal
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, override_settings
from .invoicing import create_invoice_for_booking, send_invoice_email
from .models import ConsultationBooking, CustomerProfile, ElectricianBooking, Invoice, InvoiceLine, OnCallBooking, ServiceBooking
from .views import _create_booking_invoice_draft


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BookingInvoiceLifecycleTests(TestCase):
    def bookings(self):
        return [
            ConsultationBooking.objects.create(full_name='Consultation', email='customer@example.com', consultation_price=500),
            ServiceBooking.objects.create(account_type='private', full_name='Service', email='customer@example.com', hourly_rate_snapshot=500),
            ElectricianBooking.objects.create(full_name='Electrician', email='customer@example.com', hourly_rate_snapshot=500),
            OnCallBooking.objects.create(email='customer@example.com', estimated_total=500),
        ]

    def test_bookings_only_create_drafts_without_sending(self):
        for booking in self.bookings():
            with self.subTest(booking=type(booking).__name__):
                with self.captureOnCommitCallbacks(execute=True):
                    invoice = _create_booking_invoice_draft(booking)
                self.assertEqual(invoice.status, Invoice.Status.DRAFT)
                self.assertIsNone(invoice.sent_at)
                self.assertEqual(create_invoice_for_booking(booking), invoice)
        self.assertEqual(len(mail.outbox), 0)

    def test_free_consultation_creates_no_invoice_or_customer(self):
        booking = ConsultationBooking.objects.create(full_name='Free', consultation_price=0)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(_create_booking_invoice_draft(booking))
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(CustomerProfile.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_send_requires_completion_and_uses_reviewed_price(self):
        for booking in self.bookings():
            with self.subTest(booking=type(booking).__name__):
                invoice = create_invoice_for_booking(booking)
                with self.assertRaisesMessage(ValueError, 'work must be completed'):
                    send_invoice_email(invoice)
                invoice.refresh_from_db()
                self.assertIsNone(invoice.sent_at)
                booking.status = 'completed'
                booking.save(update_fields=['status'])
                invoice = Invoice.objects.get(pk=invoice.pk)
                line = invoice.lines.first()
                line.unit_price_ex_vat = Decimal('900.00')
                line.save()
                with patch('electricity.invoicing.invoice_pdf_bytes', return_value=b'%PDF-test'):
                    self.assertTrue(send_invoice_email(invoice))
                self.assertEqual(invoice.invoice_total, Decimal('1125.00'))
        self.assertEqual(len(mail.outbox), 4)

    def test_existing_free_consultation_invoice_cannot_be_sent(self):
        booking = ConsultationBooking.objects.create(full_name='Free', consultation_price=0, status='completed')
        customer = CustomerProfile.objects.create(full_name='Free')
        invoice = Invoice.objects.create(customer=customer, recipient_email='customer@example.com', consultation_booking=booking)
        InvoiceLine.objects.create(invoice=invoice, description='Old charge', unit_price_ex_vat=100)
        with self.assertRaisesMessage(ValueError, 'Free consultations'):
            send_invoice_email(invoice)
        self.assertEqual(len(mail.outbox), 0)

    def test_zero_total_cannot_be_sent(self):
        customer = CustomerProfile.objects.create(full_name='Zero')
        invoice = Invoice.objects.create(customer=customer, recipient_email='customer@example.com')
        with self.assertRaisesMessage(ValueError, 'zero total'):
            send_invoice_email(invoice)
        self.assertEqual(len(mail.outbox), 0)
