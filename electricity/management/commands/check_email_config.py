"""Inspect effective mail routing without sending mail or printing passwords."""

from email.utils import parseaddr

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.mail.backends.smtp import EmailBackend
from django.utils.module_loading import import_string

from electricity.email_backend import invoice_email_connection, support_email_connection


class Command(BaseCommand):
    help = "Check email accounts and sender routing without sending any messages."

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
        self.stdout.write(self.style.SUCCESS(
            "Local configuration checked. No SMTP login or email delivery was attempted. "
            "Verify SPF/DKIM/DMARC results in a received message's headers."
        ))
