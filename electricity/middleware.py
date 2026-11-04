from django.utils.deprecation import MiddlewareMixin

from .form_protection import reject_public_submission


class PublicFormSpamProtectionMiddleware(MiddlewareMixin):
    """Identify public submissions; views reserve limits after validating input."""

    direct_forms = {
        "contact", "support", "for_brf", "careers", "career_detail", "feedback",
        "outside_area", "request_flow_submit", "password_reset", "signup",
    }
    # Only final booking steps count, not browsing or filling intermediate steps.
    final_steps = {
        "quote_request_step": (3, "electricity_quote_request"),
        "electrician_booking_step": (8, "electricity_electrician_booking"),
        "service_booking_step": (6, "electricity_service_booking"),
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
            for key, value in request.session.get("electricity_booking", {}).items():
                if key in {"email", "phone", "full_name"} or key not in data:
                    data[key] = value
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

        if name == "career_detail":
            data["job"] = view_kwargs.get("slug", "")
        if name == "outside_area":
            data.update(flow=view_kwargs.get("flow", ""), zip_code=view_kwargs.get("zip_code", ""))
        scope = "careers" if name == "career_detail" else name
        request.public_submission_context = (scope, data)
        if name == "password_reset":
            from .forms import UsernameOrEmailPasswordResetForm
            if UsernameOrEmailPasswordResetForm(request.POST).is_valid():
                return reject_public_submission(request)
        return None
