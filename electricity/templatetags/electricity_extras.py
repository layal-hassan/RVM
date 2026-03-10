from functools import lru_cache
from pathlib import Path

from django import template
from django.utils.translation import gettext as _
from electricity.admin_site import electricity_admin_site
from electricity.models import ElectricalService

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
def file_display_name(value):
    if not value:
        return "-"

    original_name = getattr(value, "original_name", "")
    if original_name:
        return original_name

    file_obj = getattr(value, "file", None)
    if file_obj and getattr(file_obj, "name", ""):
        return Path(file_obj.name).name

    name = getattr(value, "name", "")
    if name:
        return Path(name).name

    return str(value)


@register.filter
def pretty_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "-"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "-"
    return value


@lru_cache(maxsize=1)
def _service_title_map():
    return {
        str(service.id): service.title
        for service in ElectricalService.objects.all().only("id", "title")
    }


_LIST_VALUE_LABELS = {
    "coverage_times": {
        "evenings": _("Evenings"),
        "nights": _("Nights"),
        "weekends": _("Weekends & holidays"),
    },
    "coverage_scope": {
        "power_outages": _("Power outages"),
        "fuse_boards": _("Fuse boards"),
        "common_areas": _("Common areas"),
        "critical_systems": _("Critical systems"),
        "general_faults": _("General faults"),
    },
    "availability_days": {
        "mon": _("Mon"),
        "tue": _("Tue"),
        "wed": _("Wed"),
        "thu": _("Thu"),
        "fri": _("Fri"),
        "sat": _("Sat"),
        "sun": _("Sun"),
    },
    "interests": {
        "upgrades": _("Electrical upgrades"),
        "lighting": _("Lighting solutions"),
        "ev": _("EV charging"),
        "automation": _("Home automation"),
        "maintenance": _("Maintenance"),
    },
}


def _humanize_field_item(field_name, item):
    if field_name == "services":
        return _service_title_map().get(str(item), str(item))
    return str(_LIST_VALUE_LABELS.get(field_name, {}).get(item, item))


@register.filter
def display_value(obj, field_name):
    try:
        value = getattr(obj, field_name)
    except Exception:
        return "-"

    display_method = getattr(obj, f"get_{field_name}_display", None)
    if callable(display_method) and not isinstance(value, (list, tuple)):
        display_value_result = display_method()
        return display_value_result or "-"

    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value in (None, "", [], ()):
        return "-"
    if isinstance(value, (list, tuple)):
        return ", ".join(_humanize_field_item(field_name, item) for item in value if item not in (None, "")) or "-"
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
