"""Database-backed limits shared by all Django workers, without external services."""

import datetime
import ipaddress
import json

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import PublicFormSubmissionBucket


def allow_quick_quote(request, email, token):
    now = timezone.now()
    PublicFormSubmissionBucket.objects.filter(expires_at__lte=now).delete()
    # REMOTE_ADDR is server-provided. Do not trust a user-supplied X-Forwarded-For.
    # The deployment's trusted proxy must supply the real client REMOTE_ADDR.
    limits = [("token", token, 1, 7200, False)]
    for scope, value, maximum, seconds, windowed in limits:
        window = int(now.timestamp()) // seconds if windowed else "once"
        key = salted_hmac("quick-quote-limit", f"{scope}:{window}:{value}", algorithm="sha256").hexdigest()
        expiry = (
            datetime.datetime.fromtimestamp((window + 1) * seconds, tz=datetime.timezone.utc)
            if windowed else now + datetime.timedelta(seconds=seconds)
        )
        bucket, _ = PublicFormSubmissionBucket.objects.get_or_create(
            key=key, defaults={"expires_at": expiry},
        )
        # The conditional SQL update is atomic, including concurrent workers.
        if not PublicFormSubmissionBucket.objects.filter(pk=bucket.pk, count__lt=maximum).update(count=F("count") + 1):
            return False
    return True


def client_ip(request):
    """Accept forwarded addresses only through explicitly trusted proxy networks."""
    peer = request.META.get("REMOTE_ADDR", "")
    try:
        address = ipaddress.ip_address(peer)
        networks = [ipaddress.ip_network(value) for value in settings.FORM_TRUSTED_PROXY_NETWORKS]
        if not any(address in network for network in networks):
            return str(address)
        chain = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        for value in reversed(chain):
            address = ipaddress.ip_address(value.strip())
            if not any(address in network for network in networks):
                return str(address)
        return str(address)
    except ValueError:
        return peer or "unknown"


def normalized_email(value):
    value = str(value or "").strip().casefold()
    local, separator, domain = value.partition("@")
    if separator and domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0].replace(".", "")
        return f"{local}@gmail.com"
    return value


def normalized_phone(value):
    digits = "".join(str(int(char)) for char in str(value or "") if char.isdecimal())
    if digits.startswith("00"):
        digits = digits[2:]
    # Swedish local and international spellings identify the same phone.
    if digits.startswith("46") and len(digits) >= 10:
        digits = "0" + digits[2:].lstrip("0")
    return digits


def public_submission_retry_after(request, scope, data):
    """Return zero if allowed, otherwise seconds remaining in the limiting window."""
    now = timezone.now()
    PublicFormSubmissionBucket.objects.filter(expires_at__lte=now).delete()
    email = normalized_email(data.get("email"))
    phone = normalized_phone(data.get("phone"))
    limits = [
        ("ip", client_ip(request), 5, 600),
        ("ip-day", client_ip(request), 20, 86400),
    ]
    for name, value in (("email", email), ("phone", phone)):
        if value:
            limits.extend([(name, value, 3, 3600), (name + "-day", value, 5, 86400)])

    # Only meaningful input affects duplicate detection; extra attacker-chosen
    # fields, CSRF masks and fresh form tokens cannot change the fingerprint.
    fields = (
        "full_name", "message", "details", "project_details", "work_description",
        "request_type", "inquiry_type", "service", "services_json", "job",
        "additional_information", "recurring_issues", "additional_notes",
        "preferred_date", "preferred_time", "preferred_time_slot", "street_address",
        "consent", "confirm", "terms", "website",
    )
    content = {key: " ".join(str(data.get(key, "")).casefold().split()) for key in fields}
    content.update(email=email, phone=phone, scope=scope)
    fingerprint = json.dumps(content, sort_keys=True, ensure_ascii=True)
    # A duplicate bucket expires 10 minutes after the first attempt, avoiding
    # fixed-window boundary replays.
    limits.append(("duplicate", fingerprint, 1, 600))
    for name, value, maximum, seconds in limits:
        window = int(now.timestamp()) // seconds if name != "duplicate" else "once"
        key = salted_hmac("public-form-limit", f"{name}:{window}:{value}", algorithm="sha256").hexdigest()
        expiry = (
            datetime.datetime.fromtimestamp((window + 1) * seconds, tz=datetime.timezone.utc)
            if name != "duplicate" else now + datetime.timedelta(seconds=seconds)
        )
        bucket, _ = PublicFormSubmissionBucket.objects.get_or_create(key=key, defaults={"expires_at": expiry})
        if not PublicFormSubmissionBucket.objects.filter(pk=key, count__lt=maximum).update(count=F("count") + 1):
            return max(1, int((bucket.expires_at - now).total_seconds()) + 1)
    return 0
