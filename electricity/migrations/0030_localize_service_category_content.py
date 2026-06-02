from django.db import migrations


LANGUAGES = ("en", "ar", "sv")


def translated_payload(mapping, translated_fields):
    payload = dict(mapping)
    for key in translated_fields:
        value = mapping.get(key, "")
        for lang in LANGUAGES:
            payload[f"{key}_{lang}"] = value
    return payload


def localize_service_category_content(apps, schema_editor):
    ServiceCategoryPage = apps.get_model("electricity", "ServiceCategoryPage")
    ServiceCategorySection = apps.get_model("electricity", "ServiceCategorySection")
    ServiceCategoryItem = apps.get_model("electricity", "ServiceCategoryItem")

    ServiceCategoryPage.objects.all().delete()

    page_definitions = [
        {
            "theme": "electrical",
            "slug": "electrical-installations",
            "name": "Electrical Installations",
            "nav_label": "Electrical Installations",
            "teaser": "Core electrical installation services and infrastructure upgrades.",
            "hero_eyebrow": "Electrical Installations",
            "hero_title": "Electrical",
            "hero_highlight": "Installations",
            "hero_description": "Professional electrical installation work, panel upgrades, wiring, ventilation connections, and lighting points.",
            "notice_text": "Manage all electrical installation categories from this page.",
            "specs_title": "Technical Specifications",
            "faq_title": "Common Inquiries",
            "cta_title": "Plan Your Installation",
            "cta_description": "Use this page for electrical infrastructure, safety upgrades, and related installation services.",
            "order": 1,
            "sections": [
                {
                    "kind": "products",
                    "title": "Electrical Installation Categories",
                    "subtitle": "Core services",
                    "description": "The standard electrical installation categories used across the site.",
                    "order": 1,
                    "items": [
                        "Basic Electrical Work",
                        "Panels & Switchboards",
                        "Wiring & Cabling",
                        "Ventilation Connections",
                        "Lighting Points",
                    ],
                }
            ],
        },
        {
            "theme": "smart",
            "slug": "smart-home-ev-charging",
            "name": "Smart Home & EV Charging",
            "nav_label": "Smart Home & EV Charging",
            "teaser": "Smart home systems, automation, sensors, and EV charging categories.",
            "hero_eyebrow": "Smart Home & EV Charging",
            "hero_title": "Smart Home &",
            "hero_highlight": "EV Charging",
            "hero_description": "Residential automation, smart lighting, intelligent controls, and EV charging infrastructure.",
            "notice_text": "Manage all smart home and EV charging categories from this page.",
            "specs_title": "Service Specifications",
            "faq_title": "Common Inquiries",
            "cta_title": "Build Your Smart Ecosystem",
            "cta_description": "Use this page for automation, intelligent controls, and EV charging services.",
            "order": 2,
            "sections": [
                {
                    "kind": "products",
                    "title": "Smart Home Categories",
                    "subtitle": "Automation",
                    "description": "Primary smart home service categories.",
                    "order": 1,
                    "items": [
                        "Smart Lighting",
                        "Sensors & Timers",
                        "Thermostats",
                        "Smart Home Setup",
                    ],
                },
                {
                    "kind": "products",
                    "title": "EV Charging Categories",
                    "subtitle": "Electric vehicle infrastructure",
                    "description": "EV-focused categories for installation and upgrades.",
                    "order": 2,
                    "items": [
                        "Home Charging",
                        "Smart Charging",
                        "Outdoor Charging",
                        "Safety Upgrades",
                        "Troubleshooting",
                    ],
                },
            ],
        },
        {
            "theme": "lighting",
            "slug": "lighting-appliances",
            "name": "Lighting & Appliances",
            "nav_label": "Lighting & Appliances",
            "teaser": "Interior and exterior lighting, plus appliance-related service categories.",
            "hero_eyebrow": "Lighting & Appliances",
            "hero_title": "Lighting &",
            "hero_highlight": "Appliances",
            "hero_description": "Interior illumination, exterior lighting, facade accents, and appliance-related installations.",
            "notice_text": "Manage all lighting and appliance categories from this page.",
            "specs_title": "Technical Comparison",
            "faq_title": "Common Inquiries",
            "cta_title": "Design the Right Atmosphere",
            "cta_description": "Use this page for lighting layouts, appliance integrations, and related upgrades.",
            "order": 3,
            "sections": [
                {
                    "kind": "products",
                    "title": "Interior Lighting",
                    "subtitle": "Indoor environments",
                    "description": "Standard interior lighting categories.",
                    "order": 1,
                    "items": [
                        "Bathroom Lighting",
                        "Living Room Lighting",
                        "Kitchen Lighting",
                        "Built-In Lighting",
                        "Accent Lighting",
                        "Track Lighting",
                    ],
                },
                {
                    "kind": "products",
                    "title": "Exterior Lighting",
                    "subtitle": "Outdoor spaces",
                    "description": "Standard exterior lighting categories.",
                    "order": 2,
                    "items": [
                        "Pathway Lighting",
                        "Garden Lighting",
                        "Patio & Deck Lighting",
                        "Facade Lighting",
                        "Architectural Lighting",
                        "Decorative Outdoor",
                    ],
                },
                {
                    "kind": "products",
                    "title": "Appliances",
                    "subtitle": "Home appliances",
                    "description": "Appliance service categories.",
                    "order": 3,
                    "items": [
                        "Kitchen Appliances",
                        "Laundry Appliances",
                    ],
                },
            ],
        },
    ]

    for page_data in page_definitions:
        sections = page_data.pop("sections")
        page = ServiceCategoryPage.objects.create(
            is_active=True,
            **translated_payload(
                page_data,
                translated_fields=(
                    "name",
                    "nav_label",
                    "teaser",
                    "hero_eyebrow",
                    "hero_title",
                    "hero_highlight",
                    "hero_description",
                    "notice_text",
                    "specs_title",
                    "faq_title",
                    "cta_title",
                    "cta_description",
                ),
            ),
        )
        for section_data in sections:
            items = section_data.pop("items")
            section = ServiceCategorySection.objects.create(
                page=page,
                **translated_payload(
                    section_data,
                    translated_fields=("title", "subtitle", "description"),
                ),
            )
            for index, item_title in enumerate(items, start=1):
                ServiceCategoryItem.objects.create(
                    section=section,
                    **translated_payload(
                        {
                            "title": item_title,
                            "order": index,
                        },
                        translated_fields=("title",),
                    ),
                )


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0029_reset_service_category_content"),
    ]

    operations = [
        migrations.RunPython(localize_service_category_content, migrations.RunPython.noop),
    ]
