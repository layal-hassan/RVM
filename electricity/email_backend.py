"""SMTP backend tuned for connections that reset on large TLS writes."""

import smtplib

from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend


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
