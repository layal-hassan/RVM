from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.utils.deprecation import MiddlewareMixin

from .form_protection import public_submission_retry_after


class PublicFormSpamProtectionMiddleware(MiddlewareMixin):
    """Limit public submissions before views create records or send email."""

    direct_forms = {
        "contact", "support", "for_brf", "careers", "career_detail", "feedback",
        "outside_area", "request_flow_submit", "password_reset", "signup",
    }
    # Only final booking steps count, not browsing or filling intermediate steps.
    final_steps = {
        "quote_request_step": (3, "electricity_quote_request"),
        "electrician_booking_step": (8, "electricity_electrician_booking"),
        "service_booking_step": (11, "electricity_service_booking"),
        "on_call_booking_step": (4, "electricity_on_call_booking"),
        "legacy_booking_step": (7, "electricity_booking"),
    }

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if request.method != "POST" or not match or match.app_name != "electricity":
            return None
        name = match.url_name
        data = request.POST.dict()
        if name == "home":
            if data.get("form_type") != "quick_quote":
                return None
            from .forms import QuickQuoteForm
            if not QuickQuoteForm(request.POST).is_valid():
                return None
        elif name == "booking_step_7":
            data.update(request.session.get("electricity_booking", {}))
        elif name in self.final_steps:
            step, session_key = self.final_steps[name]
            if view_kwargs.get("step") != step:
                return None
            # Session data supplies the contact identity used by the final step.
            # Arbitrary POST contact values must not override that identity.
            session_data = request.session.get(session_key, {})
            for key, value in session_data.items():
                if key in {"email", "phone", "full_name"} or key not in data:
                    data[key] = value
        elif name not in self.direct_forms:
            return None

        scope = "careers" if name == "career_detail" else name
        retry_after = public_submission_retry_after(request, scope, data)
        if not retry_after:
            return None
        response = HttpResponse(
            _("Too many or repeated requests. Please try again later or contact us by phone."),
            status=429, content_type="text/plain; charset=utf-8",
        )
        response["Retry-After"] = str(retry_after)
        response["Cache-Control"] = "no-store"
        return response
