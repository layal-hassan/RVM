"""Inspect effective mail routing without sending mail or printing passwords."""

from email.utils import parseaddr

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail import EmailMessage
from django.utils.module_loading import import_string

from electricity.email_backend import company_email_recipients, invoice_email_connection, send_company_email, support_email_connection


class Command(BaseCommand):
    help = "Check email routing; optionally send a labelled test to each configured company mailbox."

    def add_arguments(self, parser):
        parser.add_argument("--send-test", action="store_true", help="Send one test per distinct company mailbox (never to customers).")

    def handle(self, *args, **options):
        self.stdout.write(f"Backend: {settings.EMAIL_BACKEND}")
        if not issubclass(import_string(settings.EMAIL_BACKEND), EmailBackend):
            raise CommandError("The configured backend does not deliver mail over SMTP.")
        self.stdout.write(f"SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        if not settings.EMAIL_HOST:
            raise CommandError("EMAIL_HOST is missing.")
        if settings.EMAIL_USE_TLS == settings.EMAIL_USE_SSL:
            raise CommandError("Enable exactly one of EMAIL_USE_TLS and EMAIL_USE_SSL.")

        for role, factory, sender in (
            ("Support", support_email_connection, settings.SUPPORT_FROM_EMAIL),
            ("Bookings", support_email_connection, settings.BOOKING_FROM_EMAIL),
            ("Contact/careers", support_email_connection, settings.DEFAULT_FROM_EMAIL),
            ("Invoices", invoice_email_connection, settings.INVOICE_FROM_EMAIL),
        ):
            connection = factory()
            self.stdout.write(f"{role}: From={sender}; SMTP account={connection.username}")
            if parseaddr(sender)[1].casefold() != connection.username.casefold():
                self.stdout.write(self.style.WARNING(
                    "  Sender differs from login: confirm this address is an authorized sender/alias."
                ))
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise CommandError("Default SMTP account is incomplete (used by Django system mail).")
        self.stdout.write(f"Django default SMTP account: {settings.EMAIL_HOST_USER}")
        for label, sender in (
            ("Default sender", settings.DEFAULT_FROM_EMAIL),
            ("Server sender", settings.SERVER_EMAIL),
        ):
            if parseaddr(sender)[1].casefold() != settings.EMAIL_HOST_USER.casefold():
                self.stdout.write(self.style.WARNING(
                    f"{label} ({sender}) differs from the default SMTP account; "
                    "confirm send-as permission or use matching credentials."
                ))
        destinations = {}
        for workflow, label in (("contact", "Contact/quotes/feedback"), ("service", "Bookings"), ("support", "Support"), ("careers", "Careers")):
            recipients = company_email_recipients(workflow)
            self.stdout.write(f"{label} recipient(s): {', '.join(recipients)}")
            for recipient in recipients:
                destinations.setdefault(recipient.casefold(), {"address": recipient, "labels": []})["labels"].append(label)
        if not options["send_test"]:
            self.stdout.write(self.style.SUCCESS(
                "Configuration checked. No SMTP login or email delivery was attempted. "
                "Use --send-test to check company mailbox delivery."
            ))
            return
        for destination in destinations.values():
            address = destination["address"]
            try:
                send_company_email(EmailMessage(
                    subject="RWM EL - Company notification delivery test",
                    body=(
                        "This is a requested delivery test for RWM EL company notifications.\n\n"
                        f"Company mailbox: {address}\n"
                        f"Request types: {', '.join(destination['labels'])}\n\n"
                        "No customer request was created and no customer emails were sent.\n"
                        "SMTP acceptance confirms submission to the mail server; receipt must be checked in this mailbox."
                    ),
                    from_email=settings.SUPPORT_FROM_EMAIL,
                    to=[address],
                ))
            except Exception as error:
                raise CommandError(f"Company delivery test failed for {address}: {type(error).__name__}: {error}") from error
            self.stdout.write(self.style.SUCCESS(f"Mail server accepted the test for {address}. Check its inbox/spam folder to confirm receipt."))
