"""SMTP backend tuned for connections that reset on large TLS writes."""

import smtplib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend
from django.utils.module_loading import import_string


class _ChunkedSendMixin:
    """Send SMTP payloads in small writes to avoid VPN/proxy connection resets."""

    chunk_size = 4096

    def send(self, data):
        if self.sock is None:
            raise smtplib.SMTPServerDisconnected("please run connect() first")
        if isinstance(data, str):
            data = data.encode("ascii")
        try:
            for start in range(0, len(data), self.chunk_size):
                self.sock.sendall(data[start:start + self.chunk_size])
        except OSError:
            self.close()
            raise smtplib.SMTPServerDisconnected("Server not connected")


class ChunkedSMTP(_ChunkedSendMixin, smtplib.SMTP):
    pass


class ChunkedSMTPSSL(_ChunkedSendMixin, smtplib.SMTP_SSL):
    pass


class EmailBackend(DjangoSMTPBackend):
    @property
    def connection_class(self):
        return ChunkedSMTPSSL if self.use_ssl else ChunkedSMTP


def _smtp_connection(username, password):
    """Build an authenticated SMTP connection without exposing credentials."""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    # Custom SMTP backends need not contain "smtp" in their import path.
    if not issubclass(import_string(backend), DjangoSMTPBackend):
        return None
    if not username or not password:
        raise ImproperlyConfigured(
            "SMTP account requires both a username and a password. "
            "Configure the matching SUPPORT_EMAIL_HOST_* or INVOICE_EMAIL_HOST_* pair."
        )
    return get_connection(
        backend=backend,
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=username,
        password=password,
        use_tls=settings.EMAIL_USE_TLS,
        use_ssl=settings.EMAIL_USE_SSL,
        timeout=settings.EMAIL_TIMEOUT,
    )


def support_email_connection():
    return _smtp_connection(
        getattr(settings, "SUPPORT_EMAIL_HOST_USER", settings.EMAIL_HOST_USER),
        getattr(settings, "SUPPORT_EMAIL_HOST_PASSWORD", settings.EMAIL_HOST_PASSWORD),
    )


def invoice_email_connection():
    return _smtp_connection(
        getattr(settings, "INVOICE_EMAIL_HOST_USER", settings.EMAIL_HOST_USER),
        getattr(settings, "INVOICE_EMAIL_HOST_PASSWORD", settings.EMAIL_HOST_PASSWORD),
    )
