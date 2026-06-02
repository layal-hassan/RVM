from functools import lru_cache
from pathlib import Path
from collections import OrderedDict

from django import template
from django.urls import reverse
from django.utils.translation import gettext as _
from electricity.admin_site import electricity_admin_site
from electricity.models import (
    ElectricalService,
    ServiceCategoryContentBlock,
    ServiceCategoryFAQ,
    ServiceCategoryItem,
    ServiceCategoryPage,
    ServiceCategorySection,
    ServiceCategorySpecRow,
    ServiceDetailFAQ,
    ServiceDetailContentBlock,
    ServiceDetailItem,
    ServiceDetailPage,
    ServiceDetailSection,
    ServiceDetailSpecRow,
)

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


@register.simple_tag
def service_category_pages():
    return ServiceCategoryPage.objects.filter(is_active=True).prefetch_related("service_pages").order_by("order", "name")


@register.simple_tag
def service_menu_groups(category_page):
    grouped = OrderedDict()
    for service_page in category_page.service_pages.filter(is_active=True).order_by("order", "name"):
        key = (service_page.menu_group or "").strip()
        grouped.setdefault(key, [])
        grouped[key].append(service_page)
    return list(grouped.items())


def _category_page_for_object(obj):
    if not obj:
        return None
    if isinstance(obj, ServiceCategoryPage):
        return obj
    if isinstance(obj, (ServiceCategorySection, ServiceCategorySpecRow, ServiceCategoryFAQ, ServiceCategoryContentBlock)):
        try:
            return obj.page
        except Exception:
            return None
    if isinstance(obj, ServiceCategoryItem):
        try:
            return obj.section.page
        except Exception:
            return None
    return None


def _service_page_for_object(obj):
    if not obj:
        return None
    if isinstance(obj, ServiceDetailPage):
        return obj
    if isinstance(obj, (ServiceDetailSection, ServiceDetailSpecRow, ServiceDetailFAQ, ServiceDetailContentBlock)):
        try:
            return obj.page
        except Exception:
            return None
    if isinstance(obj, ServiceDetailItem):
        try:
            return obj.section.page
        except Exception:
            return None
    return None


@register.simple_tag
def record_preview_url(obj):
    category_page = _category_page_for_object(obj)
    if category_page and getattr(category_page, "slug", ""):
        return reverse("electricity:service_category_detail", kwargs={"slug": category_page.slug})
    service_page = _service_page_for_object(obj)
    if service_page and getattr(service_page, "slug", ""):
        return reverse("electricity:service_detail", kwargs={"slug": service_page.slug})
    return ""


@register.simple_tag
def record_dashboard_page_edit_url(obj):
    category_page = _category_page_for_object(obj)
    if category_page and getattr(category_page, "pk", None):
        return reverse("electricity:dashboard_service_category_pages_edit", kwargs={"pk": category_page.pk})
    service_page = _service_page_for_object(obj)
    if service_page and getattr(service_page, "pk", None):
        return reverse("electricity:dashboard_service_pages_edit", kwargs={"pk": service_page.pk})
    return ""


@register.simple_tag
def record_dashboard_section_edit_url(obj):
    if isinstance(obj, ServiceCategoryItem):
        try:
            if getattr(obj.section, "pk", None):
                return reverse("electricity:dashboard_service_category_sections_edit", kwargs={"pk": obj.section.pk})
        except Exception:
            return ""
    if isinstance(obj, ServiceDetailItem):
        try:
            if getattr(obj.section, "pk", None):
                return reverse("electricity:dashboard_service_page_sections_edit", kwargs={"pk": obj.section.pk})
        except Exception:
            return ""
    return ""


@register.simple_tag
def dashboard_related_actions(obj):
    actions = []

    def add(label, url):
        if url:
            actions.append({"label": label, "url": url})

    if isinstance(obj, ServiceCategoryPage) and getattr(obj, "pk", None):
        add("Add Block", f"{reverse('electricity:dashboard_service_category_content_blocks_add')}?page={obj.pk}")
        add("Add Section", f"{reverse('electricity:dashboard_service_category_sections_add')}?page={obj.pk}")
        add("Add Spec", f"{reverse('electricity:dashboard_service_category_specs_add')}?page={obj.pk}")
        add("Add FAQ", f"{reverse('electricity:dashboard_service_category_faq_add')}?page={obj.pk}")
        add("Add Service", f"{reverse('electricity:dashboard_service_pages_add')}?parent_category={obj.pk}")
        return actions

    if isinstance(obj, ServiceCategoryContentBlock):
        page = _category_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Block", f"{reverse('electricity:dashboard_service_category_content_blocks_add')}?page={page.pk}")
            add("Add Section", f"{reverse('electricity:dashboard_service_category_sections_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_category_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_category_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceCategorySection):
        page = _category_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Item", f"{reverse('electricity:dashboard_service_category_items_add')}?section={obj.pk}")
            add("Add Block", f"{reverse('electricity:dashboard_service_category_content_blocks_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_category_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_category_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceCategoryItem):
        try:
            if getattr(obj.section, "pk", None):
                add("Add Item", f"{reverse('electricity:dashboard_service_category_items_add')}?section={obj.section.pk}")
        except Exception:
            pass
        return actions

    if isinstance(obj, ServiceCategorySpecRow):
        page = _category_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Section", f"{reverse('electricity:dashboard_service_category_sections_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_category_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_category_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceCategoryFAQ):
        page = _category_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Section", f"{reverse('electricity:dashboard_service_category_sections_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_category_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_category_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceDetailPage) and getattr(obj, "pk", None):
        add("Add Block", f"{reverse('electricity:dashboard_service_page_content_blocks_add')}?page={obj.pk}")
        add("Add Section", f"{reverse('electricity:dashboard_service_page_sections_add')}?page={obj.pk}")
        add("Add Spec", f"{reverse('electricity:dashboard_service_page_specs_add')}?page={obj.pk}")
        add("Add FAQ", f"{reverse('electricity:dashboard_service_page_faq_add')}?page={obj.pk}")
        return actions

    if isinstance(obj, ServiceDetailContentBlock):
        page = _service_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Block", f"{reverse('electricity:dashboard_service_page_content_blocks_add')}?page={page.pk}")
            add("Add Section", f"{reverse('electricity:dashboard_service_page_sections_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_page_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_page_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceDetailSection):
        page = _service_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Item", f"{reverse('electricity:dashboard_service_page_items_add')}?section={obj.pk}")
            add("Add Block", f"{reverse('electricity:dashboard_service_page_content_blocks_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_page_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_page_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceDetailItem):
        try:
            if getattr(obj.section, "pk", None):
                add("Add Item", f"{reverse('electricity:dashboard_service_page_items_add')}?section={obj.section.pk}")
        except Exception:
            pass
        return actions

    if isinstance(obj, ServiceDetailSpecRow):
        page = _service_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Block", f"{reverse('electricity:dashboard_service_page_content_blocks_add')}?page={page.pk}")
            add("Add Section", f"{reverse('electricity:dashboard_service_page_sections_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_page_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_page_faq_add')}?page={page.pk}")
        return actions

    if isinstance(obj, ServiceDetailFAQ):
        page = _service_page_for_object(obj)
        if page and getattr(page, "pk", None):
            add("Add Block", f"{reverse('electricity:dashboard_service_page_content_blocks_add')}?page={page.pk}")
            add("Add Section", f"{reverse('electricity:dashboard_service_page_sections_add')}?page={page.pk}")
            add("Add Spec", f"{reverse('electricity:dashboard_service_page_specs_add')}?page={page.pk}")
            add("Add FAQ", f"{reverse('electricity:dashboard_service_page_faq_add')}?page={page.pk}")
        return actions

    return actions
