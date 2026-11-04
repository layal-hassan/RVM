"""Durable company notifications. Customer confirmations never enter this outbox."""

import datetime
import logging
import uuid
from email import policy
from email.message import Message
from email.parser import BytesParser

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.db.models import F, Q
from django.utils import timezone

from .email_backend import support_email_connection
from .models import CompanyEmailDelivery

logger = logging.getLogger(__name__)
RETRY_DELAYS = (60, 300, 900, 3600, 14400)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


class _StoredMIME(Message):
    def as_bytes(self, unixfrom=False, linesep="\n", **kwargs):
        return super().as_bytes(unixfrom=unixfrom, policy=policy.SMTP.clone(linesep=linesep))


class _StoredEmail(EmailMessage):
    def __init__(self, delivery):
        super().__init__(subject=delivery.subject, from_email=delivery.from_email, to=delivery.recipients)
        self.payload = bytes(delivery.payload)

    def message(self):
        return BytesParser(_class=_StoredMIME, policy=policy.SMTP).parsebytes(self.payload)


def _due(now):
    return Q(status=CompanyEmailDelivery.Status.PENDING, next_attempt_at__lte=now) | Q(
        status=CompanyEmailDelivery.Status.SENDING, locked_until__lte=now,
    )


def attempt_company_email(delivery_id, *, message=None, raise_errors=False):
    now = timezone.now()
    claim = uuid.uuid4()
    claimed = CompanyEmailDelivery.objects.filter(pk=delivery_id).filter(_due(now)).filter(
        attempts__lt=MAX_ATTEMPTS,
    ).update(
        status=CompanyEmailDelivery.Status.SENDING, attempts=F("attempts") + 1,
        claim_token=claim,
        locked_until=now + datetime.timedelta(seconds=max(600, settings.EMAIL_TIMEOUT * 3)),
        updated_at=now,
    )
    if not claimed:
        return 0
    delivery = CompanyEmailDelivery.objects.get(pk=delivery_id, claim_token=claim)
    try:
        outgoing = message if message is not None else _StoredEmail(delivery)
        if settings.EMAIL_BACKEND in {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
        }:
            raise ImproperlyConfigured("The configured company email backend does not deliver mail.")
        # Account/configuration failures must happen after the message is saved.
        outgoing.connection = support_email_connection()
        if outgoing.send(fail_silently=False) != 1:
            raise RuntimeError("The email backend did not accept the company notification.")
    except Exception as error:
        exhausted = delivery.attempts >= MAX_ATTEMPTS
        retry_at = None if exhausted else timezone.now() + datetime.timedelta(seconds=RETRY_DELAYS[delivery.attempts - 1])
        # Preserve useful diagnostics without copying SMTP payloads or credentials.
        reason = type(error).__name__
        smtp_code = getattr(error, "smtp_code", None)
        if isinstance(smtp_code, int):
            reason += f" ({smtp_code})"
        CompanyEmailDelivery.objects.filter(pk=delivery_id, claim_token=claim).update(
            status=CompanyEmailDelivery.Status.FAILED if exhausted else CompanyEmailDelivery.Status.PENDING,
            next_attempt_at=retry_at, locked_until=None, claim_token=None,
            last_error=reason, updated_at=timezone.now(),
        )
        logger.warning("Company email %s failed; attempt=%s status=%s error=%s", delivery_id, delivery.attempts, "failed" if exhausted else "pending", reason)
        if raise_errors:
            raise
        return 0
    CompanyEmailDelivery.objects.filter(pk=delivery_id, claim_token=claim).update(
        status=CompanyEmailDelivery.Status.ACCEPTED, accepted_at=timezone.now(),
        next_attempt_at=None, locked_until=None, claim_token=None, last_error="",
        payload=b"", updated_at=timezone.now(),
    )
    logger.info("Company email %s accepted by mail backend; attempt=%s", delivery_id, delivery.attempts)
    return 1


def enqueue_company_email(message):
    mime = message.message()
    # Reuse this identity for the immediate attempt and every retry.
    for header in ("Message-ID", "Date"):
        message.extra_headers[header] = mime[header]
    delivery = CompanyEmailDelivery.objects.create(
        subject=message.subject, from_email=message.from_email,
        recipients=message.recipients(), message_id=mime["Message-ID"],
        payload=mime.as_bytes(linesep="\r\n"),
    )
    if attempt_company_email(delivery.pk, message=message, raise_errors=True):
        return 1
    delivery.refresh_from_db(fields=["status"])
    if delivery.status == CompanyEmailDelivery.Status.ACCEPTED:
        return 1
    raise RuntimeError("The company notification is saved and awaiting the retry worker.")


def retry_due_company_emails(limit=50):
    now = timezone.now()
    CompanyEmailDelivery.objects.filter(
        status=CompanyEmailDelivery.Status.SENDING, locked_until__lte=now, attempts__gte=MAX_ATTEMPTS,
    ).update(status=CompanyEmailDelivery.Status.FAILED, next_attempt_at=None, locked_until=None,
             claim_token=None, last_error="Worker stopped during final attempt", updated_at=now)
    delivery_ids = list(CompanyEmailDelivery.objects.filter(_due(now)).filter(
        attempts__lt=MAX_ATTEMPTS,
    ).order_by("created_at").values_list("pk", flat=True)[:limit])
    accepted = sum(attempt_company_email(delivery_id) for delivery_id in delivery_ids)
    return {"selected": len(delivery_ids), "accepted": accepted}
