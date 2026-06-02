from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from electricity.models import (
    ServiceCategoryPage,
    ServiceDetailFAQ,
    ServiceDetailItem,
    ServiceDetailPage,
    ServiceDetailSection,
    ServiceDetailSpecRow,
)


def _lines(*items: str) -> str:
    return "\n".join(item for item in items if item)


def _translated_value(model, field_name: str, value):
    setattr(model, field_name, value)
    for language_code, _label in settings.LANGUAGES:
        translated_name = f"{field_name}_{language_code}"
        if hasattr(model, translated_name):
            setattr(model, translated_name, value)


SMART_PAGE_DEMOS = {
    "smart-lighting": {
        "image_url": "https://images.pexels.com/photos/1393363/pexels-photo-1393363.jpeg?cs=srgb&dl=pexels-fotios-photos-1393363.jpg&fm=jpg",
        "teaser": "Demo content for layered smart lighting scenes, switches, and app control.",
        "hero_title": "Smart Lighting",
        "hero_highlight": "Scenes & Control",
        "hero_description": "A test page for tunable white, dimming zones, app scenes, and hallway automation. This content is intentionally distinct so the page is easy to recognize during QA.",
        "hero_card_title": "Demo Snapshot",
        "hero_card_lines": _lines("3 lighting zones", "2-way switching", "Voice + app presets"),
        "notice_text": "QA demo: living room lighting page with scene-based copy and image.",
        "specs_title": "Lighting Presets",
        "specs_subtitle": "Example configuration tiers used only for visual testing.",
        "spec_col_1": "Feature",
        "spec_col_2": "Entry",
        "spec_col_3": "Family",
        "spec_col_4": "Showcase",
        "faq_title": "Lighting Questions",
        "faq_subtitle": "Dummy FAQ entries for template review.",
        "cta_title": "Need smarter room lighting?",
        "cta_description": "Use this demo page to validate hero media, card spacing, CTA alignment, and FAQ behavior on a content-heavy lighting layout.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Scene Starter",
                "subtitle": "Living room and hallway",
                "description": "Basic app-controlled dimming with evening and night scenes for two connected areas.",
                "price_text": "From 2,900 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Warm dimming profile", "2 smart switches", "Mobile app onboarding"),
                "included_title": "Includes",
                "included_lines": _lines("Scene programming", "Switch replacement", "User handover"),
            },
            {
                "badge": "Popular",
                "title": "Mood Layer Kit",
                "subtitle": "Accent + ceiling blend",
                "description": "A more visual setup with ceiling spots, cabinet accent strips, and timed automations.",
                "price_text": "From 5,400 SEK",
                "price_note": "test data",
                "meta_lines": _lines("3 preset scenes", "Timer routines", "Multi-zone grouping"),
                "included_title": "Includes",
                "included_lines": _lines("Controller setup", "Scene tuning", "Dimmer calibration"),
            },
            {
                "badge": "Flagship",
                "title": "Whole-Floor Atmosphere",
                "subtitle": "Unified scene control",
                "description": "A larger demonstration package for open-plan homes that need layered lighting and occupancy logic.",
                "price_text": "From 9,800 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Hallway motion trigger", "Kitchen scene sync", "Guest mode preset"),
                "included_title": "Includes",
                "included_lines": _lines("Room-by-room mapping", "Fine tuning", "Final walkthrough"),
            },
        ],
        "feature_cards": [
            {
                "title": "Evening Relax Scene",
                "description": "Lowered brightness, warmer color temperature, and one-tap activation.",
            },
            {
                "title": "Away Mode Lighting",
                "description": "Randomized timing to simulate occupancy while the home is empty.",
            },
        ],
        "spec_rows": [
            ("Control method", "Switch", "App", "Voice", "Hybrid"),
            ("Color handling", "Warm white", "Tunable", "RGB accents", "Mixed rooms"),
            ("Automation", "Manual", "Timer", "Motion", "Presence + scenes"),
            ("Best for", "Small room", "Apartment", "Family zone", "Show home"),
        ],
        "faqs": [
            ("Can this demo page reuse one image across cards?", "Yes. The goal here is to make the page visually distinct during testing, not to represent final production assets."),
            ("Why are the prices written like this?", "They are intentionally obvious placeholders so nobody mistakes them for final commercial pricing."),
            ("What should QA check first?", "Check the hero image crop, the card spacing, and whether the CTA still reads clearly on smaller screens."),
        ],
    },
    "sensors-timers": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/PIR%20Motion%20Detector.jpg",
        "teaser": "Demo content for occupancy sensing, timed relays, and hallway triggers.",
        "hero_title": "Sensors & Timers",
        "hero_highlight": "Motion Logic",
        "hero_description": "This test page focuses on occupancy sensors, stairwell timers, utility-room automation, and predictable trigger logic for small spaces.",
        "hero_card_title": "Test Scope",
        "hero_card_lines": _lines("Hallway PIR trigger", "Bathroom timer relay", "Utility room occupancy off-delay"),
        "notice_text": "QA demo: sensor-driven page with motion-oriented messaging.",
        "specs_title": "Automation Timing",
        "specs_subtitle": "Reference values for testing tables and longer labels.",
        "spec_col_1": "Setting",
        "spec_col_2": "Quick",
        "spec_col_3": "Balanced",
        "spec_col_4": "Extended",
        "faq_title": "Sensor Questions",
        "faq_subtitle": "Template-only sample answers.",
        "cta_title": "Want motion-based automation?",
        "cta_description": "Use this page when checking layouts with short technical terms, installation logic, and narrow card content.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Hallway Sensor Start",
                "subtitle": "Simple walk-through detection",
                "description": "A lightweight test offer for corridors, entries, and storage rooms.",
                "price_text": "From 1,800 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Single PIR unit", "Adjustable timeout", "Manual override retained"),
                "included_title": "Includes",
                "included_lines": _lines("Basic calibration", "Coverage test", "Timer setup"),
            },
            {
                "badge": "Popular",
                "title": "Timer Relay Set",
                "subtitle": "Bathrooms and utility zones",
                "description": "Adds delayed shutoff logic where lights or fans should not cut instantly.",
                "price_text": "From 3,100 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Fan overrun", "Wet-room timing", "Low-touch use"),
                "included_title": "Includes",
                "included_lines": _lines("Timer programming", "Functional test", "Usage handover"),
            },
            {
                "badge": "Flagship",
                "title": "Multi-Sensor Routine",
                "subtitle": "Linked trigger zones",
                "description": "A demo setup with several sensor points and different timeout profiles per room.",
                "price_text": "From 6,200 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Zoned triggers", "Separate delay values", "Occupancy mapping"),
                "included_title": "Includes",
                "included_lines": _lines("Trigger tuning", "Blind-spot review", "Scenario testing"),
            },
        ],
        "feature_cards": [
            {"title": "Short-Pass Mode", "description": "Useful for entries where the light only needs a brief hold time."},
            {"title": "Night Corridor Mode", "description": "Keeps pathways visible without full brightness during late hours."},
        ],
        "spec_rows": [
            ("Trigger type", "Motion", "Motion + timer", "Occupancy", "Mixed logic"),
            ("Delay off", "30 sec", "2 min", "5 min", "10 min"),
            ("Typical room", "Entry", "Bathroom", "Utility", "Corridor chain"),
            ("Manual override", "No", "Optional", "Yes", "Scene aware"),
        ],
        "faqs": [
            ("Why use a motion detector image here?", "It immediately differentiates this page from the other smart-home service pages during testing."),
            ("Should every card have a photo?", "Not necessarily. This demo uses text-heavy cards so you can inspect spacing without relying on many media assets."),
            ("Can these values be edited later in admin?", "Yes. The command only seeds demo data into the existing database records."),
        ],
    },
    "thermostats": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/ColorTouch%20touch%20screen%20thermostat.jpg",
        "teaser": "Demo content for room thermostats, schedules, and comfort control.",
        "hero_title": "Thermostats",
        "hero_highlight": "Comfort Schedules",
        "hero_description": "A distinct thermostat demo page for daily schedules, comfort presets, and room-by-room temperature control review.",
        "hero_card_title": "Preset Modes",
        "hero_card_lines": _lines("Home", "Sleep", "Away"),
        "notice_text": "QA demo: thermostat page with schedule-focused copy and touchscreen imagery.",
        "specs_title": "Temperature Profiles",
        "specs_subtitle": "Example setup levels for interface validation.",
        "spec_col_1": "Profile",
        "spec_col_2": "Basic",
        "spec_col_3": "Daily",
        "spec_col_4": "Adaptive",
        "faq_title": "Thermostat Questions",
        "faq_subtitle": "Sample content for accordion behavior.",
        "cta_title": "Test a comfort-control layout",
        "cta_description": "This page is useful when validating dense copy, small technical labels, and CTA readability over image backgrounds.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Room Thermostat Swap",
                "subtitle": "Straight replacement",
                "description": "Test content for replacing a manual control with a programmable room thermostat.",
                "price_text": "From 2,200 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Daily schedule", "Touchscreen setup", "Comfort preset"),
                "included_title": "Includes",
                "included_lines": _lines("Basic scheduling", "Calibration", "User training"),
            },
            {
                "badge": "Popular",
                "title": "Week Planner Setup",
                "subtitle": "Routine-based comfort",
                "description": "Adds workday and weekend planning with simple away setbacks.",
                "price_text": "From 3,900 SEK",
                "price_note": "test data",
                "meta_lines": _lines("5+2 scheduling", "Wake and sleep presets", "Holiday hold"),
                "included_title": "Includes",
                "included_lines": _lines("Program creation", "Energy advice", "Final review"),
            },
            {
                "badge": "Flagship",
                "title": "Multi-Room Climate Demo",
                "subtitle": "Coordinated comfort zones",
                "description": "A visual testing setup for separate temperature logic in bedrooms, living areas, and home offices.",
                "price_text": "From 7,400 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Zone naming", "Setback logic", "Priority room control"),
                "included_title": "Includes",
                "included_lines": _lines("Room tuning", "Schedule verification", "Walkthrough"),
            },
        ],
        "feature_cards": [
            {"title": "Sleep Setback", "description": "Reduces overnight output and restores comfort automatically in the morning."},
            {"title": "Guest Override", "description": "Temporary comfort mode without changing the weekly schedule."},
        ],
        "spec_rows": [
            ("Scheduling", "Manual", "Daily", "Weekly", "Adaptive"),
            ("Display", "Buttons", "Touch", "Color touch", "App mirror"),
            ("Zones", "1", "2", "4", "8"),
            ("Best fit", "Single room", "Apartment", "Family home", "Large villa"),
        ],
        "faqs": [
            ("Why is the copy more comfort-oriented here?", "Because the thermostat page should read differently from lighting, EV, and diagnostics pages."),
            ("Are these package names final?", "No. They are intentionally artificial to make it obvious this is seeded demo content."),
            ("What should be checked in responsive view?", "Focus on the spec table, CTA text wrapping, and the open state of the first FAQ item."),
        ],
    },
    "smart-home-setup": {
        "image_url": "https://loremflickr.com/1600/900/smart,home,tablet?lock=104",
        "teaser": "Demo content for whole-home onboarding, hub setup, and app mapping.",
        "hero_title": "Smart Home Setup",
        "hero_highlight": "Onboarding Flow",
        "hero_description": "A QA-focused page for initial smart-home setup, device pairing, naming conventions, and household handover.",
        "hero_card_title": "Setup Checklist",
        "hero_card_lines": _lines("Hub online", "Rooms named", "Scenes tested"),
        "notice_text": "QA demo: onboarding page with whole-home setup language.",
        "specs_title": "Deployment Levels",
        "specs_subtitle": "Visual testing tiers for setup-focused copy.",
        "spec_col_1": "Scope",
        "spec_col_2": "Small",
        "spec_col_3": "Connected",
        "spec_col_4": "Advanced",
        "faq_title": "Setup Questions",
        "faq_subtitle": "Sample content for the setup template.",
        "cta_title": "Review a full onboarding page",
        "cta_description": "Use this seeded page to verify how broader setup copy behaves compared with product-specific services.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Starter Pairing",
                "subtitle": "Up to 5 devices",
                "description": "A small demo package for first-time setup with naming, room assignment, and app access.",
                "price_text": "From 2,600 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Phone pairing", "Room labels", "Basic scene test"),
                "included_title": "Includes",
                "included_lines": _lines("Device join", "App access check", "Owner handover"),
            },
            {
                "badge": "Popular",
                "title": "Home Map Launch",
                "subtitle": "Structured device organization",
                "description": "Groups devices by room and introduces sensible names, routines, and user access.",
                "price_text": "From 4,700 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Zone structure", "Scene labels", "Routine draft"),
                "included_title": "Includes",
                "included_lines": _lines("Naming standard", "Access review", "Scenario validation"),
            },
            {
                "badge": "Flagship",
                "title": "Whole-Home Commissioning",
                "subtitle": "Large residence demo",
                "description": "A broader seeded package for testing complex cards and denser onboarding copy.",
                "price_text": "From 8,600 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Multi-user access", "Device audit", "Automation acceptance"),
                "included_title": "Includes",
                "included_lines": _lines("Room structure", "Routine checks", "Final training"),
            },
        ],
        "feature_cards": [
            {"title": "Naming Convention Pass", "description": "Ensures switches, rooms, and scenes are labeled consistently across the home."},
            {"title": "Household Handover", "description": "Confirms every user can reach the app and understands the core routines."},
        ],
        "spec_rows": [
            ("Device count", "1-5", "6-15", "16-30", "30+"),
            ("User setup", "Owner only", "2 users", "Family", "Family + guests"),
            ("Automation", "None", "Basic scenes", "Room routines", "Whole-home logic"),
            ("Best use", "Small flat", "Apartment", "Townhouse", "Large home"),
        ],
        "faqs": [
            ("Why is this page broader than the others?", "Because it represents commissioning and setup, not one hardware category."),
            ("Can QA distinguish it quickly?", "Yes. The headline, checklist, and onboarding language are intentionally different from the technical pages."),
            ("Does the seed replace manual edits?", "Running the command again will refresh the demo data for these smart-category service pages."),
        ],
    },
    "home-charging": {
        "image_url": "https://loremflickr.com/1600/900/ev,charger,home?lock=105",
        "teaser": "Demo content for residential wallbox installs and home charging routines.",
        "hero_title": "Home Charging",
        "hero_highlight": "Residential Wallbox",
        "hero_description": "A dedicated demo page for garage and driveway EV charging, focused on homeowner language and simple daily charging habits.",
        "hero_card_title": "Typical Install",
        "hero_card_lines": _lines("Garage wallbox", "Load review", "Cable reach check"),
        "notice_text": "QA demo: residential EV charging page with home-use framing.",
        "specs_title": "Home Charging Options",
        "specs_subtitle": "Illustrative tiers to validate EV page layouts.",
        "spec_col_1": "Option",
        "spec_col_2": "Essentials",
        "spec_col_3": "Balanced",
        "spec_col_4": "Premium",
        "faq_title": "Home Charging Questions",
        "faq_subtitle": "Residential sample content.",
        "cta_title": "Compare a home EV page",
        "cta_description": "This seeded page is built to look obviously different from smart-home automation pages while still using the same template.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Garage Charger Start",
                "subtitle": "Simple home installation",
                "description": "Baseline test content for a single EV wallbox near the household parking spot.",
                "price_text": "From 9,500 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Single parking bay", "Cable reach review", "Basic breaker check"),
                "included_title": "Includes",
                "included_lines": _lines("Mounting", "Startup test", "Owner walkthrough"),
            },
            {
                "badge": "Popular",
                "title": "Daily Charge Setup",
                "subtitle": "Convenient overnight routine",
                "description": "Adds scheduling and a tidier cable layout for repeat daily use at home.",
                "price_text": "From 13,800 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Timer schedule", "Cable management", "Current limit review"),
                "included_title": "Includes",
                "included_lines": _lines("Schedule setup", "Load settings", "Usage briefing"),
            },
            {
                "badge": "Flagship",
                "title": "Dual-Car Driveway Demo",
                "subtitle": "Expanded home charging",
                "description": "A richer seeded scenario for larger homes with more than one EV in rotation.",
                "price_text": "From 19,600 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Two-vehicle planning", "Driveway routing", "Household charging policy"),
                "included_title": "Includes",
                "included_lines": _lines("Layout review", "Load balance prep", "Final testing"),
            },
        ],
        "feature_cards": [
            {"title": "Overnight Ready", "description": "Focuses on predictable evening plug-in and full battery by morning."},
            {"title": "Family Parking Logic", "description": "Helps distinguish between a single-user charger and shared household use."},
        ],
        "spec_rows": [
            ("Mounting", "Indoor wall", "Garage wall", "Driveway wall", "Pedestal"),
            ("Cable reach", "Short", "Standard", "Extended", "Custom route"),
            ("User type", "Single EV", "Couple", "Family", "Two-EV home"),
            ("Best fit", "Apartment garage", "Private garage", "Driveway", "Large property"),
        ],
        "faqs": [
            ("Why is this page more residential?", "Because it is meant to contrast clearly with the smart charging and outdoor charging variants."),
            ("Can we keep these price labels?", "Only as placeholder data. They are for template testing, not launch content."),
            ("What should QA inspect here?", "Check image cropping in hero and CTA, plus the longer EV package names in the card grid."),
        ],
    },
    "smart-charging": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Portable%20EV%20Charger%20Wallbox%20Unit%20with%20Red%20CEE%20Plug%20White%20Background%20EV%20WALL%20BOX%20EVWALLBOX.png",
        "teaser": "Demo content for load-aware charging, scheduling, and dynamic current control.",
        "hero_title": "Smart Charging",
        "hero_highlight": "Load-Aware EV",
        "hero_description": "A separate demo page for app scheduling, load balancing, and current-aware EV charging behavior.",
        "hero_card_title": "Control Logic",
        "hero_card_lines": _lines("Off-peak schedule", "Dynamic current cap", "App notifications"),
        "notice_text": "QA demo: smart charging page with logic-driven EV copy.",
        "specs_title": "Charging Intelligence",
        "specs_subtitle": "Placeholder data for more technical EV messaging.",
        "spec_col_1": "Function",
        "spec_col_2": "Basic",
        "spec_col_3": "Managed",
        "spec_col_4": "Dynamic",
        "faq_title": "Smart Charging Questions",
        "faq_subtitle": "Dummy FAQ set for this variant.",
        "cta_title": "Review a logic-heavy EV page",
        "cta_description": "This content is intentionally more technical than the home charging page so the difference is obvious in navigation tests.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Scheduled Charge Start",
                "subtitle": "Simple app timers",
                "description": "Demonstrates basic charging windows for cheaper overnight energy periods.",
                "price_text": "From 11,400 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Start/stop windows", "App pairing", "User schedule presets"),
                "included_title": "Includes",
                "included_lines": _lines("App config", "Timer setup", "Simple handover"),
            },
            {
                "badge": "Popular",
                "title": "Managed Load Profile",
                "subtitle": "Current-aware charging",
                "description": "A test package focused on balancing vehicle charging against home consumption peaks.",
                "price_text": "From 15,900 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Current cap", "Peak smoothing", "Alert setup"),
                "included_title": "Includes",
                "included_lines": _lines("Load settings", "Scenario test", "Performance review"),
            },
            {
                "badge": "Flagship",
                "title": "Dynamic Charging Demo",
                "subtitle": "Most technical option",
                "description": "Structured to make this page feel more advanced than standard wallbox installation content.",
                "price_text": "From 22,300 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Tariff awareness", "Dynamic response", "Usage reporting"),
                "included_title": "Includes",
                "included_lines": _lines("Rule tuning", "App walkthrough", "Edge-case testing"),
            },
        ],
        "feature_cards": [
            {"title": "Off-Peak Automation", "description": "Delays charging until the preferred time window starts."},
            {"title": "Load Response", "description": "Reduces current when other large household loads are active."},
        ],
        "spec_rows": [
            ("Scheduling", "Manual", "Timed", "Load aware", "Dynamic"),
            ("Alerts", "None", "Basic", "Push notice", "Detailed"),
            ("Energy logic", "Static", "Window based", "Priority based", "Adaptive"),
            ("Best fit", "Single EV", "Daily commuter", "Busy home", "Power user"),
        ],
        "faqs": [
            ("Why use a different image type here?", "A product-style render helps separate smart charging from the more lifestyle-oriented home charging page."),
            ("Is this still demo content?", "Yes. The technical wording is deliberate so testers can compare tone differences between related EV pages."),
            ("What makes this page unique in QA?", "The emphasis on control logic, load balancing, and scheduling labels."),
        ],
    },
    "outdoor-charging": {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/7/71/EV_Charging_Station_%2853857454477%29.jpg",
        "teaser": "Demo content for driveway, facade, and weather-exposed EV charging points.",
        "hero_title": "Outdoor Charging",
        "hero_highlight": "Driveway Ready",
        "hero_description": "A test page centered on outdoor EV charging locations, cable routing, and weather exposure around the home exterior.",
        "hero_card_title": "Outdoor Focus",
        "hero_card_lines": _lines("Facade mount", "Weather-exposed run", "Parking alignment"),
        "notice_text": "QA demo: outdoor EV page with exterior-installation language.",
        "specs_title": "Outdoor Install Variants",
        "specs_subtitle": "Sample values for exterior-facing charging layouts.",
        "spec_col_1": "Aspect",
        "spec_col_2": "Wall",
        "spec_col_3": "Driveway",
        "spec_col_4": "Freestanding",
        "faq_title": "Outdoor Charging Questions",
        "faq_subtitle": "Visual testing content only.",
        "cta_title": "Test an exterior charging layout",
        "cta_description": "This page is intended to look and read different from indoor home charging, with more focus on weather and routing.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Facade Charger Point",
                "subtitle": "Wall-mounted outside",
                "description": "A simple outdoor placement for houses where the vehicle parks close to the building.",
                "price_text": "From 10,700 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Short exterior run", "Wall weather check", "Parking reach review"),
                "included_title": "Includes",
                "included_lines": _lines("Mounting", "Basic sealing", "Startup test"),
            },
            {
                "badge": "Popular",
                "title": "Driveway Access Setup",
                "subtitle": "Longer approach route",
                "description": "Adds more routing and placement considerations for detached parking areas.",
                "price_text": "From 16,100 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Route planning", "Cable protection", "Vehicle approach line"),
                "included_title": "Includes",
                "included_lines": _lines("Placement review", "Exterior finishing", "Function test"),
            },
            {
                "badge": "Flagship",
                "title": "Freestanding Post Demo",
                "subtitle": "Standalone outdoor solution",
                "description": "The most visibly different seeded EV package, built around exterior-only placement.",
                "price_text": "From 24,500 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Post location", "Ground path coordination", "Outdoor finish"),
                "included_title": "Includes",
                "included_lines": _lines("Layout test", "Exposure review", "Final handover"),
            },
        ],
        "feature_cards": [
            {"title": "Weather-Facing Position", "description": "Helps QA distinguish exterior installation language from indoor garage content."},
            {"title": "Parking Reach Review", "description": "Focuses on cable length, mount height, and daily approach angle."},
        ],
        "spec_rows": [
            ("Placement", "Facade", "Fence line", "Driveway edge", "Post mount"),
            ("Exposure", "Sheltered", "Semi-open", "Open", "High weather"),
            ("Cable path", "Short", "Surface route", "Protected route", "Ground route"),
            ("Best fit", "Near wall", "Small driveway", "Detached parking", "Open exterior"),
        ],
        "faqs": [
            ("Why emphasize weather here?", "Because it cleanly separates this page from the garage-oriented home charging content."),
            ("Can the same template still feel different?", "Yes. Distinct copy, specs, and imagery are enough to make page switching obvious."),
            ("What is the main responsive risk?", "Long outdoor package names may wrap earlier, so card height consistency should be checked."),
        ],
    },
    "safety-upgrades": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Circuit%20breaker.jpg",
        "teaser": "Demo content for breaker checks, protective upgrades, and EV readiness reviews.",
        "hero_title": "Safety Upgrades",
        "hero_highlight": "Protection First",
        "hero_description": "A placeholder page for protective upgrades, panel checks, and safer EV charging readiness around existing installations.",
        "hero_card_title": "Safety Review",
        "hero_card_lines": _lines("Breaker capacity", "Protection devices", "Installation readiness"),
        "notice_text": "QA demo: safety-first EV support page with panel-oriented content.",
        "specs_title": "Upgrade Paths",
        "specs_subtitle": "Testing data for protection and readiness language.",
        "spec_col_1": "Review area",
        "spec_col_2": "Check",
        "spec_col_3": "Upgrade",
        "spec_col_4": "Prepared",
        "faq_title": "Safety Questions",
        "faq_subtitle": "Placeholder FAQ content.",
        "cta_title": "Compare a protection-oriented page",
        "cta_description": "This seeded page intentionally reads more cautious and assessment-driven than the other EV variants.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Readiness Check",
                "subtitle": "Basic pre-install review",
                "description": "A visual testing package for inspection-style content before EV charging is added.",
                "price_text": "From 1,500 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Existing panel review", "Protection status", "Notes for next step"),
                "included_title": "Includes",
                "included_lines": _lines("Checklist pass", "Visible issue notes", "Recommendation summary"),
            },
            {
                "badge": "Popular",
                "title": "Protection Upgrade Plan",
                "subtitle": "Safer charging prep",
                "description": "Adds more detail around protective components and charging readiness improvements.",
                "price_text": "From 6,900 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Device review", "Risk reduction", "Capacity planning"),
                "included_title": "Includes",
                "included_lines": _lines("Upgrade outline", "Safety notes", "Final review"),
            },
            {
                "badge": "Flagship",
                "title": "Panel & EV Readiness Demo",
                "subtitle": "Broader upgrade scenario",
                "description": "A seeded package for testing dense content where the page should feel more diagnostic than promotional.",
                "price_text": "From 12,800 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Panel path", "Device path", "EV prep status"),
                "included_title": "Includes",
                "included_lines": _lines("Detailed notes", "Upgrade mapping", "Owner handover"),
            },
        ],
        "feature_cards": [
            {"title": "Readiness Assessment", "description": "Positions the page as an evaluation step before or alongside charging installation."},
            {"title": "Protective Upgrade Focus", "description": "Keeps the tone more cautious and technical than the installation pages."},
        ],
        "spec_rows": [
            ("Scope", "Visual check", "Basic upgrade", "Prepared install", "Expanded review"),
            ("Output", "Notes", "Recommendation", "Upgrade path", "Action plan"),
            ("Primary focus", "Condition", "Protection", "Readiness", "Future growth"),
            ("Best fit", "Unsure owner", "Old panel", "EV prep", "Large upgrade"),
        ],
        "faqs": [
            ("Why does this page sound less sales-driven?", "Because the goal is to distinguish safety and readiness content from direct installation offers."),
            ("Is the image final?", "No. It is a downloaded demo asset chosen to make the page visually different during review."),
            ("What should be checked in the table?", "Look at long labels and make sure the fifth column still aligns correctly."),
        ],
    },
    "troubleshooting": {
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Digital%20multimeter.jpg",
        "teaser": "Demo content for fault finding, charger diagnostics, and intermittent issue review.",
        "hero_title": "Troubleshooting",
        "hero_highlight": "Fault Finding",
        "hero_description": "A clearly different diagnostics page for charging interruptions, app errors, breaker trips, and inconsistent charging sessions.",
        "hero_card_title": "Diagnostic Flow",
        "hero_card_lines": _lines("Symptom capture", "Fault isolation", "Next action"),
        "notice_text": "QA demo: diagnostics page with investigation-driven copy.",
        "specs_title": "Diagnostic Routes",
        "specs_subtitle": "Dummy data for a troubleshooting-oriented service page.",
        "spec_col_1": "Issue type",
        "spec_col_2": "Basic",
        "spec_col_3": "Intermittent",
        "spec_col_4": "Complex",
        "faq_title": "Troubleshooting Questions",
        "faq_subtitle": "Example diagnostics FAQ content.",
        "cta_title": "Validate a diagnostics layout",
        "cta_description": "This page should feel more investigative than the rest of the section, making it useful for navigation and content-difference testing.",
        "packages": [
            {
                "badge": "Demo Pack",
                "title": "Single-Fault Visit",
                "subtitle": "One visible issue",
                "description": "A small seeded package for obvious charger or control problems that need first-pass diagnosis.",
                "price_text": "From 2,100 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Symptom review", "Basic checks", "Next-step note"),
                "included_title": "Includes",
                "included_lines": _lines("Initial diagnosis", "Owner summary", "Test run"),
            },
            {
                "badge": "Popular",
                "title": "Intermittent Charging Review",
                "subtitle": "Harder-to-repeat faults",
                "description": "For cases where the charger sometimes works and sometimes fails without a clear pattern.",
                "price_text": "From 4,800 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Event pattern review", "Usage history", "Repeat-condition checks"),
                "included_title": "Includes",
                "included_lines": _lines("Fault isolation", "Test sequence", "Summary notes"),
            },
            {
                "badge": "Flagship",
                "title": "System Diagnosis Demo",
                "subtitle": "Complex behavior mapping",
                "description": "A more layered troubleshooting scenario to stress-test card heights and longer technical text.",
                "price_text": "From 8,900 SEK",
                "price_note": "test data",
                "meta_lines": _lines("Multiple symptoms", "Component review", "Escalation path"),
                "included_title": "Includes",
                "included_lines": _lines("Extended checks", "Issue mapping", "Recommendations"),
            },
        ],
        "feature_cards": [
            {"title": "Trip Event Review", "description": "Captures patterns around breaker trips and failed charge starts."},
            {"title": "App/Error Mapping", "description": "Separates user-reported symptoms from confirmed electrical causes."},
        ],
        "spec_rows": [
            ("Fault pattern", "Obvious", "Occasional", "Intermittent", "Multi-factor"),
            ("Visit goal", "Identify", "Repeat", "Isolate", "Escalate"),
            ("Report detail", "Short", "Standard", "Detailed", "Investigation log"),
            ("Best fit", "Simple issue", "Homeowner complaint", "Recurring fault", "Complex setup"),
        ],
        "faqs": [
            ("Why is this page text heavier?", "Troubleshooting naturally needs more explanation, and that makes it visually different from the installation pages."),
            ("Should this page share the same CTA wording as others?", "No. The CTA is intentionally diagnostic in tone so the distinction is easy to spot."),
            ("What QA difference matters most here?", "The contrast between investigation-style copy and the more product-style service pages."),
        ],
    },
}


class Command(BaseCommand):
    help = "Seed distinct demo content for Smart Home & EV Charging service detail pages."

    def handle(self, *args, **options):
        try:
            category_page = ServiceCategoryPage.objects.get(theme=ServiceCategoryPage.Theme.SMART)
        except ServiceCategoryPage.DoesNotExist as exc:
            raise CommandError("Smart Home & EV Charging category page was not found.") from exc

        for slug, payload in SMART_PAGE_DEMOS.items():
            page = ServiceDetailPage.objects.filter(parent_category=category_page, slug=slug).first()
            if not page:
                self.stdout.write(self.style.WARNING(f"Skipped missing page: {slug}"))
                continue
            self._seed_page(page, payload)
            self.stdout.write(self.style.SUCCESS(f"Seeded demo content: {slug}"))

    def _seed_page(self, page: ServiceDetailPage, payload: dict) -> None:
        _translated_value(page, "teaser", payload["teaser"])
        _translated_value(page, "hero_eyebrow", page.parent_category.name)
        _translated_value(page, "hero_title", payload["hero_title"])
        _translated_value(page, "hero_highlight", payload["hero_highlight"])
        _translated_value(page, "hero_description", payload["hero_description"])
        _translated_value(page, "hero_card_title", payload["hero_card_title"])
        _translated_value(page, "hero_card_lines", payload["hero_card_lines"])
        _translated_value(page, "notice_text", payload["notice_text"])
        _translated_value(page, "primary_cta_label", "Book consultation")
        page.primary_cta_url = "/consultation-booking/step-1/"
        _translated_value(page, "secondary_cta_label", "Contact team")
        page.secondary_cta_url = "/contact/"
        _translated_value(page, "specs_title", payload["specs_title"])
        _translated_value(page, "specs_subtitle", payload["specs_subtitle"])
        _translated_value(page, "spec_col_1", payload["spec_col_1"])
        _translated_value(page, "spec_col_2", payload["spec_col_2"])
        _translated_value(page, "spec_col_3", payload["spec_col_3"])
        _translated_value(page, "spec_col_4", payload["spec_col_4"])
        _translated_value(page, "faq_title", payload["faq_title"])
        _translated_value(page, "faq_subtitle", payload["faq_subtitle"])
        _translated_value(page, "cta_title", payload["cta_title"])
        _translated_value(page, "cta_description", payload["cta_description"])
        _translated_value(page, "cta_primary_label", "Start booking")
        page.cta_primary_url = "/consultation-booking/step-1/"
        _translated_value(page, "cta_secondary_label", "See all services")
        page.cta_secondary_url = "/services/"

        image_relative_path = self._download_image(page.slug, payload["image_url"])
        if image_relative_path:
            page.hero_image.name = image_relative_path
            page.cta_image.name = image_relative_path

        page.is_active = True
        page.save()

        page.sections.all().delete()
        page.spec_rows.all().delete()
        page.faqs.all().delete()

        packages_section = ServiceDetailSection.objects.create(
            page=page,
            kind=ServiceDetailSection.Kind.PRODUCTS,
            order=1,
        )
        _translated_value(packages_section, "title", "Demo Packages")
        _translated_value(packages_section, "subtitle", "Distinct placeholder packages for visual QA")
        _translated_value(
            packages_section,
            "description",
            "Each card is intentionally different so page switching in this section is easy to verify.",
        )
        packages_section.save()

        for index, package in enumerate(payload["packages"], start=1):
            item = ServiceDetailItem(section=packages_section, order=index, is_featured=index == 2)
            for field_name in [
                "badge",
                "title",
                "subtitle",
                "description",
                "price_text",
                "price_note",
                "meta_lines",
                "included_title",
                "included_lines",
            ]:
                _translated_value(item, field_name, package.get(field_name, ""))
            _translated_value(item, "cta_label", "Use this demo")
            item.cta_url = f"/services/page/{page.slug}/"
            item.save()

        features_section = ServiceDetailSection.objects.create(
            page=page,
            kind=ServiceDetailSection.Kind.FEATURES,
            order=2,
        )
        _translated_value(features_section, "title", "Typical Use Cases")
        _translated_value(features_section, "subtitle", "Short cards to stress-test compact layouts")
        _translated_value(
            features_section,
            "description",
            "These support cards are shorter than the package cards on purpose.",
        )
        features_section.save()

        for index, feature_card in enumerate(payload["feature_cards"], start=1):
            item = ServiceDetailItem(section=features_section, order=index)
            _translated_value(item, "title", feature_card["title"])
            _translated_value(item, "description", feature_card["description"])
            item.save()

        for index, row in enumerate(payload["spec_rows"], start=1):
            spec_row = ServiceDetailSpecRow(page=page, order=index)
            _translated_value(spec_row, "label", row[0])
            _translated_value(spec_row, "value_1", row[1])
            _translated_value(spec_row, "value_2", row[2])
            _translated_value(spec_row, "value_3", row[3])
            _translated_value(spec_row, "value_4", row[4])
            spec_row.save()

        for index, faq in enumerate(payload["faqs"], start=1):
            faq_item = ServiceDetailFAQ(page=page, order=index, is_active=True)
            _translated_value(faq_item, "question", faq[0])
            _translated_value(faq_item, "answer", faq[1])
            faq_item.save()

    def _download_image(self, slug: str, url: str) -> str:
        target_dir = Path(settings.MEDIA_ROOT) / "electricity" / "service_pages" / "heroes"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / f"{slug}-demo.jpg"
        if target_path.exists() and target_path.stat().st_size > 0:
            return "electricity/service_pages/heroes/" + target_path.name

        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Codex seed command)",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
        except (HTTPError, URLError, TimeoutError):
            return ""

        if not content:
            return ""

        target_path.write_bytes(content)
        return "electricity/service_pages/heroes/" + target_path.name
