from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag("electricity/partials/turnstile_widget.html")
def turnstile_widget():
    return {"enabled": settings.TURNSTILE_ENABLED, "site_key": settings.TURNSTILE_SITE_KEY}


@register.inclusion_tag("electricity/partials/turnstile_scripts.html")
def turnstile_scripts():
    return {"enabled": settings.TURNSTILE_ENABLED}
