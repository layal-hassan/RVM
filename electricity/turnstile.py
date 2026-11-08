"""Cloudflare Turnstile verification for public submissions."""

import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_submission(request, scope):
    if not settings.TURNSTILE_ENABLED:
        return None
    # A token is single-use; only validate it once within the same request.
    if getattr(request, "turnstile_verified", False):
        return None
    token = request.POST.get("cf-turnstile-response", "").strip()
    valid = False
    if token and len(token) <= 2048:
        payload = urlencode({"secret": settings.TURNSTILE_SECRET_KEY, "response": token}).encode("ascii")
        try:
            verification = Request(SITEVERIFY_URL, data=payload, headers={
                "Content-Type": "application/x-www-form-urlencoded",
            }, method="POST")
            with urlopen(verification, timeout=settings.TURNSTILE_TIMEOUT) as response:
                result = json.loads(response.read(65536))
            valid = (
                isinstance(result, dict)
                and result.get("success") is True
                and result.get("hostname", "").lower() == request.get_host().split(":", 1)[0].lower()
            )
        except (URLError, OSError, ValueError):
            # Never log tokens or the secret key; a service failure must fail closed.
            logger.warning("Turnstile verification unavailable: scope=%s", scope)
    if valid:
        request.turnstile_verified = True
        return None
    message = _("Please complete the security verification and try again.")
    if scope == "request_flow_submit":
        response = JsonResponse({"ok": False, "error": message, "verification_required": True}, status=400)
    else:
        response = render(request, "electricity/verification_failed.html", {"verification_message": message}, status=400)
    response["Cache-Control"] = "no-store"
    return response
