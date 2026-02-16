from django import template
from electricity.admin_site import electricity_admin_site

register = template.Library()


@register.filter
def split_lines(value):
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@register.filter
def attr(obj, name):
    try:
        return getattr(obj, name)
    except Exception:
        return ""


@register.filter
def pretty_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "-"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "-"
    return value


@register.simple_tag(takes_context=True)
def is_electricity_admin(context):
    request = context.get("request")
    if not request:
        return False
    user = request.user
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return electricity_admin_site.has_permission(request)
