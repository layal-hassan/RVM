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


PAGE_IMAGE_URLS = {
    "bathroom-lighting": "https://loremflickr.com/1600/900/bathroom,lighting?lock=301",
    "living-room-lighting": "https://loremflickr.com/1600/900/living-room,lighting?lock=302",
    "kitchen-lighting": "https://loremflickr.com/1600/900/kitchen,lighting?lock=303",
    "built-in-lighting": "https://loremflickr.com/1600/900/recessed,lighting?lock=304",
    "accent-lighting": "https://loremflickr.com/1600/900/accent,lighting?lock=305",
    "track-lighting": "https://loremflickr.com/1600/900/track,lighting?lock=306",
    "pathway-lighting": "https://loremflickr.com/1600/900/pathway,lighting?lock=307",
    "garden-lighting": "https://loremflickr.com/1600/900/garden,lighting?lock=308",
    "patio-deck-lighting": "https://loremflickr.com/1600/900/patio,deck,lighting?lock=309",
    "facade-lighting": "https://loremflickr.com/1600/900/facade,lighting?lock=310",
    "architectural-lighting": "https://loremflickr.com/1600/900/architectural,lighting?lock=311",
    "decorative-outdoor": "https://loremflickr.com/1600/900/outdoor,decorative,lights?lock=312",
    "kitchen-appliances": "https://loremflickr.com/1600/900/kitchen,appliances?lock=313",
    "laundry-appliances": "https://loremflickr.com/1600/900/laundry,appliances?lock=314",
}


PAGES = [
    {
        "slug": "bathroom-lighting",
        "title": "Bathroom Lighting",
        "highlight": "Mirror & Moisture Zones",
        "group": "Interior",
        "description": "A test page for vanity lighting, shower-safe fixtures, soft night guidance, and mirror clarity in small wet rooms.",
        "notice": "QA demo: bathroom page with wet-room lighting language.",
        "card_title": "Bathroom Presets",
        "card_lines": _lines("Mirror task light", "Soft night route", "Moisture-rated fixtures"),
        "spec_cols": ("Zone", "Basic", "Balanced", "Premium"),
        "packages": [
            ("Vanity Refresh", "Mirror-focused brightness for daily routines.", "From 2,400 SEK"),
            ("Warm Spa Layer", "Adds calmer indirect light for evening bathroom use.", "From 4,800 SEK"),
            ("Full Wet-Room Demo", "A richer placeholder layout for mirrors, niches, and shower zones.", "From 7,900 SEK"),
        ],
        "features": [
            ("Night Path Glow", "Keeps the route visible without full ceiling brightness."),
            ("Mirror Clarity", "Supports shaving, makeup, and morning routines with cleaner light."),
        ],
        "spec_rows": [
            ("Light focus", "Mirror", "Mirror + ceiling", "Mirror + accent", "Full layered"),
            ("Mood", "Bright", "Soft", "Spa", "Adaptive"),
            ("Best fit", "Guest WC", "Main bath", "Family bath", "Show bathroom"),
            ("Ingress protection", "Dry zone", "Nearby splash", "Wet-room aware", "High exposure"),
        ],
        "faqs": [
            ("Why is this page different from kitchen lighting?", "The copy is focused on mirrors, wet zones, and softer evening use so it reads clearly differently."),
            ("Are the prices final?", "No. They are visual placeholders only."),
            ("What should QA verify here?", "Check hero crop, short-card balance, and spec-table wrapping."),
        ],
    },
    {
        "slug": "living-room-lighting",
        "title": "Living Room Lighting",
        "highlight": "Mood Layers",
        "group": "Interior",
        "description": "A demo page centered on layered living-room scenes, reading corners, TV comfort, and everyday ambience.",
        "notice": "QA demo: living room page with comfort and scene-based copy.",
        "card_title": "Scene Stack",
        "card_lines": _lines("Ceiling wash", "Reading corner", "TV-friendly dimming"),
        "spec_cols": ("Scene", "Starter", "Family", "Showcase"),
        "packages": [
            ("Cozy Corner Start", "Simple mood layers for sofa zones and evening use.", "From 3,100 SEK"),
            ("Family Lounge Setup", "Balances social brightness and softer TV-time lighting.", "From 5,900 SEK"),
            ("Open Living Showcase", "Broader demo content for large open-plan lounge spaces.", "From 9,400 SEK"),
        ],
        "features": [
            ("Movie Mode", "Reduces glare and keeps side lighting gentle."),
            ("Reading Pocket", "Creates stronger focused light where a chair or sofa needs it."),
        ],
        "spec_rows": [
            ("Primary use", "Relax", "Family use", "Entertaining", "Mixed use"),
            ("Layer count", "2", "3", "4", "5+"),
            ("Control", "Switch", "Dimmer", "Scene button", "App + scenes"),
            ("Best fit", "Small lounge", "Apartment", "Family room", "Large salon"),
        ],
        "faqs": [
            ("Why does this page sound softer?", "It is written to feel domestic and mood-driven rather than task-heavy."),
            ("Can this page share layout with others?", "Yes, but the content is intentionally distinct for navigation testing."),
            ("What matters most in mobile view?", "Card title wrapping and the hero text balance."),
        ],
    },
    {
        "slug": "kitchen-lighting",
        "title": "Kitchen Lighting",
        "highlight": "Task & Prep",
        "group": "Interior",
        "description": "A test page for worktop visibility, under-cabinet strips, dining crossover light, and prep-focused brightness.",
        "notice": "QA demo: kitchen page with task-lighting tone.",
        "card_title": "Prep Zones",
        "card_lines": _lines("Counter task light", "Island highlight", "Dining crossover"),
        "spec_cols": ("Area", "Core", "Cook", "Chef"),
        "packages": [
            ("Countertop Start", "Entry-level demo package for clearer worktop visibility.", "From 2,900 SEK"),
            ("Island & Cabinet Set", "Adds under-cabinet lighting and focal light over the island.", "From 6,100 SEK"),
            ("Cookspace Demo", "A fuller seeded page for prep, cooking, and dining overlap.", "From 10,200 SEK"),
        ],
        "features": [
            ("Worktop Accuracy", "Supports chopping, reading labels, and prep detail."),
            ("Dining Transition", "Lets the kitchen soften when cooking ends and hosting starts."),
        ],
        "spec_rows": [
            ("Focus", "Counter", "Counter + sink", "Island + counter", "Full zone map"),
            ("Mood", "Bright", "Balanced", "Warm task", "Scene-based"),
            ("Controls", "Switch", "Dimmer", "Dual control", "Scene control"),
            ("Best fit", "Compact kitchen", "Apartment", "Family kitchen", "Designer kitchen"),
        ],
        "faqs": [
            ("How is this different from appliances pages?", "This page focuses on illumination zones, not the appliances themselves."),
            ("Why mention dining transition?", "It helps the kitchen page read differently from pure work-area pages."),
            ("What QA issue should be watched?", "Long package names and spec headings on smaller screens."),
        ],
    },
    {
        "slug": "built-in-lighting",
        "title": "Built-In Lighting",
        "highlight": "Clean Recessed Lines",
        "group": "Interior",
        "description": "A seeded page for recessed fixtures, flush ceiling detail, and minimalist integrated light layouts.",
        "notice": "QA demo: built-in page with integrated-fixture wording.",
        "card_title": "Integrated Look",
        "card_lines": _lines("Flush finish", "Discrete ceiling rhythm", "Minimalist appearance"),
        "spec_cols": ("Finish", "Simple", "Refined", "Architectural"),
        "packages": [
            ("Flush Spot Start", "Basic recessed layout for clean low-visual-noise ceilings.", "From 3,500 SEK"),
            ("Integrated Room Grid", "More structured distribution for wider rooms.", "From 6,700 SEK"),
            ("Minimalist Ceiling Demo", "A denser placeholder package for premium integrated interiors.", "From 11,500 SEK"),
        ],
        "features": [
            ("Quiet Ceiling", "Keeps fixtures visually controlled and unobtrusive."),
            ("Even Rhythm", "Spreads light more consistently through the room plan."),
        ],
        "spec_rows": [
            ("Visual style", "Discrete", "Clean", "Refined", "Architectural"),
            ("Fixture density", "Low", "Balanced", "Structured", "Grid"),
            ("Room type", "Hall", "Bedroom", "Living room", "Open-plan"),
            ("Best fit", "Renovation", "Apartment", "Family home", "High-end interior"),
        ],
        "faqs": [
            ("Why is the wording more minimalist here?", "Because integrated fixtures should feel visually cleaner than accent or track systems."),
            ("Does this page need many images?", "Not necessarily; the content itself is enough to distinguish it."),
            ("What should be checked first?", "Look at long headings and the hero card spacing."),
        ],
    },
    {
        "slug": "accent-lighting",
        "title": "Accent Lighting",
        "highlight": "Shelves & Highlights",
        "group": "Interior",
        "description": "A demo page for shelf glow, niche lighting, wall washing, and small statement details that shift mood quickly.",
        "notice": "QA demo: accent page with decorative and display-oriented language.",
        "card_title": "Highlight Points",
        "card_lines": _lines("Shelf glow", "Art focus", "Niche drama"),
        "spec_cols": ("Accent", "Subtle", "Layered", "Statement"),
        "packages": [
            ("Shelf Glow Start", "Simple placeholder content for cabinet and shelf highlights.", "From 1,900 SEK"),
            ("Artwork Accent Set", "Builds a stronger test layout around focal pieces and wall detail.", "From 4,200 SEK"),
            ("Feature Wall Demo", "Designed to stand apart from general room-lighting pages.", "From 7,600 SEK"),
        ],
        "features": [
            ("Object Focus", "Draws attention to selected objects, textures, or artwork."),
            ("Mood Lift", "Changes the feel of a room without dominating the whole ceiling plan."),
        ],
        "spec_rows": [
            ("Effect", "Soft glow", "Focused", "Layered", "Statement"),
            ("Placement", "Shelf", "Wall", "Niche", "Mixed"),
            ("Best use", "Decor", "Art", "Display storage", "Feature room"),
            ("Control", "On/off", "Dimmer", "Scene", "App scene"),
        ],
        "faqs": [
            ("Why is this page more decorative?", "Because accent lighting should feel more expressive than functional kitchen or bathroom lighting."),
            ("Is this production copy?", "No. It is seeded QA content."),
            ("What is the key visual check?", "That smaller cards still feel distinct from the larger package cards."),
        ],
    },
    {
        "slug": "track-lighting",
        "title": "Track Lighting",
        "highlight": "Directional Flexibility",
        "group": "Interior",
        "description": "A test page for directional heads, movable beam focus, and adaptable room layouts where aiming matters.",
        "notice": "QA demo: track-lighting page with adjustable beam language.",
        "card_title": "Aim Points",
        "card_lines": _lines("Moveable heads", "Flexible direction", "Room re-aiming"),
        "spec_cols": ("Setup", "Short", "Flexible", "Gallery"),
        "packages": [
            ("Linear Track Start", "Entry-level seeded package for compact directional layouts.", "From 3,300 SEK"),
            ("Flexible Room Rail", "Adds more heads and varied aiming positions.", "From 6,000 SEK"),
            ("Gallery Track Demo", "Longer test content for more dramatic directional lighting.", "From 10,800 SEK"),
        ],
        "features": [
            ("Re-Aim Later", "Helps when furniture or wall art changes over time."),
            ("Directional Control", "Makes the page feel more technical than decorative accents."),
        ],
        "spec_rows": [
            ("Rail length", "Short", "Medium", "Long", "Multi-rail"),
            ("Heads", "2", "4", "6", "8+"),
            ("Use case", "Small room", "Studio", "Living room", "Display space"),
            ("Best fit", "Rental refresh", "Apartment", "Flexible home", "Gallery-style interior"),
        ],
        "faqs": [
            ("How is this different from built-in lighting?", "Track systems emphasize adjustability, not hidden integration."),
            ("Why does the language sound more technical?", "To make the page easy to distinguish in the section menu."),
            ("What should QA watch?", "Card heights when beam-control wording wraps."),
        ],
    },
    {
        "slug": "pathway-lighting",
        "title": "Pathway Lighting",
        "highlight": "Safe Outdoor Routes",
        "group": "Exterior",
        "description": "A demo page for entrance routes, walkway visibility, low-level guiding light, and safer evening movement outdoors.",
        "notice": "QA demo: pathway page with route and safety wording.",
        "card_title": "Route Focus",
        "card_lines": _lines("Entry path", "Step visibility", "Low-glare markers"),
        "spec_cols": ("Path", "Basic", "Guided", "Premium"),
        "packages": [
            ("Entry Route Start", "Simple placeholder package for front-door path visibility.", "From 2,600 SEK"),
            ("Walkway Guide Set", "Longer seeded content for stepping lines and approach lighting.", "From 5,300 SEK"),
            ("Property Route Demo", "Broader test layout for larger garden or entry routes.", "From 8,700 SEK"),
        ],
        "features": [
            ("Step Clarity", "Makes edges and changes in level easier to read."),
            ("Low Glare", "Keeps orientation clear without harsh brightness."),
        ],
        "spec_rows": [
            ("Route size", "Short", "Medium", "Long", "Multi-path"),
            ("Brightness feel", "Soft", "Balanced", "Guided", "Statement"),
            ("Best fit", "Entry", "Drive approach", "Garden path", "Large property"),
            ("Priority", "Wayfinding", "Safety", "Wayfinding + decor", "Full exterior route"),
        ],
        "faqs": [
            ("Why is this page more safety-focused?", "Pathway lighting is about movement and orientation first."),
            ("Can it still feel decorative?", "Yes, but the seeded wording keeps it distinct from decorative outdoor pages."),
            ("What should QA check?", "Hero readability over brighter outdoor photos."),
        ],
    },
    {
        "slug": "garden-lighting",
        "title": "Garden Lighting",
        "highlight": "Planting & Texture",
        "group": "Exterior",
        "description": "A test page for planting beds, tree uplighting, texture, and layered evening garden atmosphere.",
        "notice": "QA demo: garden page with landscape and texture language.",
        "card_title": "Garden Layers",
        "card_lines": _lines("Planting beds", "Tree uplight", "Soft perimeter glow"),
        "spec_cols": ("Garden", "Small", "Layered", "Showcase"),
        "packages": [
            ("Bed Light Start", "Basic seeded package for planting edge highlights.", "From 3,000 SEK"),
            ("Tree & Border Set", "Adds more texture and depth around shrubs and trunks.", "From 6,400 SEK"),
            ("Evening Garden Demo", "A richer placeholder layout for more atmospheric outdoor scenes.", "From 11,100 SEK"),
        ],
        "features": [
            ("Texture Reveal", "Brings bark, leaves, and stone surfaces forward after dark."),
            ("Perimeter Atmosphere", "Makes the page read softer than pathway or facade lighting."),
        ],
        "spec_rows": [
            ("Focus", "Beds", "Beds + shrubs", "Trees + beds", "Full garden"),
            ("Mood", "Gentle", "Warm", "Layered", "Showcase"),
            ("Property size", "Small", "Medium", "Large", "Extended"),
            ("Best fit", "Courtyard", "Private garden", "Family yard", "Landscape-led property"),
        ],
        "faqs": [
            ("Why does this page feel more atmospheric?", "Garden lighting should read differently from route lighting and appliance pages."),
            ("Is this seeded only for visuals?", "Yes, it is demo content for layout and navigation testing."),
            ("What should be reviewed on desktop?", "The balance between longer mood text and the image area."),
        ],
    },
    {
        "slug": "patio-deck-lighting",
        "title": "Patio & Deck Lighting",
        "highlight": "Outdoor Social Zones",
        "group": "Exterior",
        "description": "A demo page for seating areas, decking edges, outdoor dining, and warm hospitality-focused exterior light.",
        "notice": "QA demo: patio page with hosting-oriented wording.",
        "card_title": "Social Lighting",
        "card_lines": _lines("Dining glow", "Deck edge light", "Conversation comfort"),
        "spec_cols": ("Deck", "Simple", "Hosting", "Showcase"),
        "packages": [
            ("Deck Edge Start", "Basic test content for step-edge and seating-area light.", "From 2,800 SEK"),
            ("Outdoor Dining Set", "Focuses the page on meals, gathering, and warmer social light.", "From 5,800 SEK"),
            ("Evening Terrace Demo", "The broadest placeholder package in this sub-group.", "From 9,900 SEK"),
        ],
        "features": [
            ("Hosting Warmth", "Supports longer evenings around tables and lounge furniture."),
            ("Edge Awareness", "Improves movement around deck levels without harshness."),
        ],
        "spec_rows": [
            ("Use", "Small seating", "Dining", "Dining + lounge", "Large terrace"),
            ("Mood", "Warm", "Welcoming", "Layered social", "Premium hospitality"),
            ("Detail", "Basic edge", "Dining focus", "Mixed zones", "Full outdoor room"),
            ("Best fit", "Balcony deck", "Patio", "Family deck", "Large terrace"),
        ],
        "faqs": [
            ("Why is the tone more social here?", "This page is meant to feel warmer and more hospitality-driven than pathway or facade lighting."),
            ("Can this be mistaken for decorative outdoor?", "Less likely, because the wording emphasizes seating and dining use."),
            ("What QA point matters here?", "Button visibility on busier exterior imagery."),
        ],
    },
    {
        "slug": "facade-lighting",
        "title": "Facade Lighting",
        "highlight": "Exterior Presence",
        "group": "Exterior",
        "description": "A seeded page for front elevation emphasis, vertical surfaces, and house identity after dark.",
        "notice": "QA demo: facade page with house-front emphasis.",
        "card_title": "Front Elevation",
        "card_lines": _lines("Wall wash", "Entry framing", "Exterior identity"),
        "spec_cols": ("Facade", "Soft", "Defined", "Showcase"),
        "packages": [
            ("Entry Front Start", "Simple seeded content for front-door and wall emphasis.", "From 3,700 SEK"),
            ("Wall Wash Setup", "Adds stronger visual definition across the house front.", "From 7,200 SEK"),
            ("Signature Facade Demo", "A more dramatic test page for bold exterior character.", "From 12,400 SEK"),
        ],
        "features": [
            ("House Presence", "Makes the building feel legible and more intentional at night."),
            ("Entry Framing", "Supports orientation while keeping the emphasis architectural."),
        ],
        "spec_rows": [
            ("Look", "Soft", "Defined", "Architectural", "Statement"),
            ("Focus", "Entry", "Entry + wall", "Facade rhythm", "Whole front"),
            ("Best fit", "Small house", "Townhouse", "Detached home", "Architectural home"),
            ("Priority", "Identity", "Identity + safety", "Exterior form", "Showcase"),
        ],
        "faqs": [
            ("How is this different from architectural lighting?", "Facade lighting centers on the house front, while architectural lighting is broader and more design-led."),
            ("Is this seeded content final?", "No. It is only there to distinguish the page clearly."),
            ("What should QA inspect?", "Headline balance against taller facade imagery."),
        ],
    },
    {
        "slug": "architectural-lighting",
        "title": "Architectural Lighting",
        "highlight": "Structure & Form",
        "group": "Exterior",
        "description": "A distinct page for design-led light composition, structural emphasis, and stronger visual storytelling across building elements.",
        "notice": "QA demo: architectural page with form-driven wording.",
        "card_title": "Form Language",
        "card_lines": _lines("Structural lines", "Material emphasis", "Composed exterior mood"),
        "spec_cols": ("Design", "Controlled", "Composed", "Signature"),
        "packages": [
            ("Form Study Start", "A small placeholder package for highlighting selected building lines.", "From 4,600 SEK"),
            ("Material Focus Set", "Adds more detail around textures, recesses, and visual rhythm.", "From 8,500 SEK"),
            ("Signature Exterior Demo", "Built to feel more design-heavy than the rest of the lighting section.", "From 14,900 SEK"),
        ],
        "features": [
            ("Material Emphasis", "Makes surfaces, recesses, and depth more legible."),
            ("Composed Night Identity", "Pushes the page toward design language instead of simple function."),
        ],
        "spec_rows": [
            ("Intent", "Highlight", "Compose", "Direct", "Signature"),
            ("Focus", "Single element", "Selected planes", "Multiple planes", "Whole composition"),
            ("Best fit", "Modern upgrade", "Renovation", "Architect-designed home", "Statement property"),
            ("Tone", "Refined", "Design-led", "Architectural", "Showpiece"),
        ],
        "faqs": [
            ("Why is this page more design-heavy?", "Because it should clearly stand apart from pathway, patio, and facade pages."),
            ("Can the same template support that?", "Yes, with distinct wording and more architectural framing."),
            ("What should be checked?", "Spec-table readability with longer design-oriented labels."),
        ],
    },
    {
        "slug": "decorative-outdoor",
        "title": "Decorative Outdoor",
        "highlight": "Festive & Expressive",
        "group": "Exterior",
        "description": "A seeded page for expressive outdoor accents, string-light mood, decorative lantern effects, and playful exterior styling.",
        "notice": "QA demo: decorative outdoor page with expressive wording.",
        "card_title": "Decor Focus",
        "card_lines": _lines("Festive string light", "Lantern mood", "Playful highlights"),
        "spec_cols": ("Decor", "Soft", "Festive", "Statement"),
        "packages": [
            ("Outdoor Glow Start", "Simple placeholder content for softer decorative evening light.", "From 1,700 SEK"),
            ("String & Lantern Set", "More obviously decorative wording for quick page differentiation.", "From 3,900 SEK"),
            ("Festive Garden Demo", "A seeded package for a more playful exterior presentation.", "From 6,800 SEK"),
        ],
        "features": [
            ("Celebration Feel", "Makes the page read more playful than the other exterior lighting pages."),
            ("Flexible Decor", "Supports temporary-feeling ambience within a permanent layout template."),
        ],
        "spec_rows": [
            ("Mood", "Soft", "Warm", "Festive", "Expressive"),
            ("Typical use", "Corner glow", "Dining decor", "Seasonal mood", "Event-like"),
            ("Best fit", "Balcony", "Patio", "Garden lounge", "Entertaining space"),
            ("Priority", "Decor", "Decor + comfort", "Mood", "Visual statement"),
        ],
        "faqs": [
            ("Why is this page more playful?", "Decorative outdoor lighting should not read the same as pathway or facade content."),
            ("Is it okay that the offers look lighter?", "Yes, that is intentional for testing the distinction."),
            ("What QA detail matters?", "That the page still feels coherent even with a softer decorative tone."),
        ],
    },
    {
        "slug": "kitchen-appliances",
        "title": "Kitchen Appliances",
        "highlight": "Hookups & Integration",
        "group": "Appliances",
        "description": "A test page for appliance connections, oven and hob support, and practical kitchen service coordination.",
        "notice": "QA demo: kitchen-appliance page with service and hookup language.",
        "card_title": "Appliance Scope",
        "card_lines": _lines("Oven hookup", "Cooktop support", "Practical kitchen coordination"),
        "spec_cols": ("Appliance", "Single", "Family", "Full kitchen"),
        "packages": [
            ("Single Appliance Visit", "Seeded content for one kitchen appliance connection or replacement.", "From 1,900 SEK"),
            ("Cook Line Setup", "A fuller page for oven, hob, and coordinated kitchen appliance support.", "From 4,900 SEK"),
            ("Kitchen Service Demo", "The broadest appliance-oriented placeholder package in this section.", "From 8,400 SEK"),
        ],
        "features": [
            ("Practical Support", "Keeps the tone more service-oriented than design-led lighting pages."),
            ("Kitchen Coordination", "Makes it easy to tell this page apart from kitchen lighting."),
        ],
        "spec_rows": [
            ("Scope", "Single unit", "Two units", "Cook line", "Multiple appliances"),
            ("Priority", "Connection", "Replacement", "Coordination", "Full service"),
            ("Best fit", "Quick visit", "Small kitchen", "Family kitchen", "Renovation"),
            ("Tone", "Practical", "Service-led", "Coordinated", "Comprehensive"),
        ],
        "faqs": [
            ("How is this different from kitchen lighting?", "This page is about appliance support and hookups, not illumination zones."),
            ("Why does it sound more practical?", "Because appliance pages should feel functional and service-driven."),
            ("What should QA verify?", "That users can distinguish kitchen lighting from kitchen appliances immediately."),
        ],
    },
    {
        "slug": "laundry-appliances",
        "title": "Laundry Appliances",
        "highlight": "Utility-Room Setup",
        "group": "Appliances",
        "description": "A seeded page for washer and dryer support, utility-room planning, and practical service around laundry areas.",
        "notice": "QA demo: laundry page with utility-room wording.",
        "card_title": "Laundry Tasks",
        "card_lines": _lines("Washer support", "Dryer setup", "Utility-room coordination"),
        "spec_cols": ("Laundry", "Basic", "Utility", "Complete"),
        "packages": [
            ("Washer Support Visit", "Seeded placeholder content for a single laundry appliance callout.", "From 1,800 SEK"),
            ("Washer & Dryer Set", "A clearer two-unit service scenario for QA differentiation.", "From 4,300 SEK"),
            ("Utility Room Demo", "Larger placeholder package for more complete laundry-area service content.", "From 7,700 SEK"),
        ],
        "features": [
            ("Utility Tone", "Keeps the page distinct from stylish lighting-oriented pages."),
            ("Service Clarity", "Positions the content around practical household tasks and support."),
        ],
        "spec_rows": [
            ("Scope", "Single unit", "Pair", "Utility pair", "Full room"),
            ("Priority", "Support", "Connection", "Replacement", "Coordination"),
            ("Best fit", "Apartment", "Family home", "Utility room", "Renovation"),
            ("Tone", "Practical", "Household", "Utility-led", "Comprehensive"),
        ],
        "faqs": [
            ("Why is this page less decorative?", "Laundry appliances should feel unmistakably practical."),
            ("Can this share the same CTA style?", "Yes, but the seeded wording is intentionally different."),
            ("What should QA check?", "That the final two appliance pages do not blur into the lighting pages."),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed distinct demo content for Lighting & Appliances service detail pages."

    def handle(self, *args, **options):
        try:
            category_page = ServiceCategoryPage.objects.get(theme=ServiceCategoryPage.Theme.LIGHTING)
        except ServiceCategoryPage.DoesNotExist as exc:
            raise CommandError("Lighting & Appliances category page was not found.") from exc

        for payload in PAGES:
            page = ServiceDetailPage.objects.filter(parent_category=category_page, slug=payload["slug"]).first()
            if not page:
                self.stdout.write(self.style.WARNING(f"Skipped missing page: {payload['slug']}"))
                continue
            self._seed_page(page, payload)
            self.stdout.write(self.style.SUCCESS(f"Seeded demo content: {payload['slug']}"))

    def _seed_page(self, page: ServiceDetailPage, payload: dict) -> None:
        _translated_value(page, "teaser", f"Demo content for {payload['title'].lower()} with clearly distinct placeholder copy.")
        _translated_value(page, "hero_eyebrow", f"Lighting & Appliances / {payload['group']}")
        _translated_value(page, "hero_title", payload["title"])
        _translated_value(page, "hero_highlight", payload["highlight"])
        _translated_value(page, "hero_description", payload["description"])
        _translated_value(page, "hero_card_title", payload["card_title"])
        _translated_value(page, "hero_card_lines", payload["card_lines"])
        _translated_value(page, "notice_text", payload["notice"])
        _translated_value(page, "primary_cta_label", "Book consultation")
        page.primary_cta_url = "/consultation-booking/step-1/"
        _translated_value(page, "secondary_cta_label", "Contact team")
        page.secondary_cta_url = "/contact/"
        _translated_value(page, "specs_title", f"{payload['title']} Demo Specs")
        _translated_value(page, "specs_subtitle", "Placeholder configuration levels for QA and layout testing.")
        _translated_value(page, "spec_col_1", payload["spec_cols"][0])
        _translated_value(page, "spec_col_2", payload["spec_cols"][1])
        _translated_value(page, "spec_col_3", payload["spec_cols"][2])
        _translated_value(page, "spec_col_4", payload["spec_cols"][3])
        _translated_value(page, "faq_title", f"{payload['title']} Questions")
        _translated_value(page, "faq_subtitle", "Dummy FAQ entries used to distinguish this page from neighboring services.")
        _translated_value(page, "cta_title", f"Review the {payload['title'].lower()} demo page")
        _translated_value(
            page,
            "cta_description",
            "This seeded page exists to make service-to-service comparison inside the menu easier during review.",
        )
        _translated_value(page, "cta_primary_label", "Start booking")
        page.cta_primary_url = "/consultation-booking/step-1/"
        _translated_value(page, "cta_secondary_label", "See all services")
        page.cta_secondary_url = "/services/"

        image_relative_path = self._download_image(page.slug, PAGE_IMAGE_URLS[page.slug])
        if image_relative_path:
            page.hero_image.name = image_relative_path
            page.cta_image.name = image_relative_path

        page.is_active = True
        page.save()

        page.sections.all().delete()
        page.spec_rows.all().delete()
        page.faqs.all().delete()

        packages_section = ServiceDetailSection.objects.create(page=page, kind=ServiceDetailSection.Kind.PRODUCTS, order=1)
        _translated_value(packages_section, "title", "Demo Packages")
        _translated_value(packages_section, "subtitle", "Deliberately different cards for page-by-page QA")
        _translated_value(packages_section, "description", "Each package is placeholder content intended to make the page visually and textually distinct.")
        packages_section.save()

        for index, package in enumerate(payload["packages"], start=1):
            item = ServiceDetailItem(section=packages_section, order=index, is_featured=index == 2)
            _translated_value(item, "badge", "Demo Pack" if index == 1 else "Popular" if index == 2 else "Flagship")
            _translated_value(item, "title", package[0])
            _translated_value(item, "description", package[1])
            _translated_value(item, "price_text", package[2])
            _translated_value(item, "price_note", "test data")
            _translated_value(item, "meta_lines", _lines(payload["group"], payload["highlight"], "Distinct seeded content"))
            _translated_value(item, "included_title", "Includes")
            _translated_value(item, "included_lines", _lines("Placeholder scope", "Visual QA content", "Template verification"))
            _translated_value(item, "cta_label", "Use this demo")
            item.cta_url = f"/services/page/{page.slug}/"
            item.save()

        features_section = ServiceDetailSection.objects.create(page=page, kind=ServiceDetailSection.Kind.FEATURES, order=2)
        _translated_value(features_section, "title", "Typical Use Cases")
        _translated_value(features_section, "subtitle", "Compact support cards for layout contrast")
        _translated_value(features_section, "description", "Shorter cards make it easier to validate mixed content density.")
        features_section.save()

        for index, feature in enumerate(payload["features"], start=1):
            item = ServiceDetailItem(section=features_section, order=index)
            _translated_value(item, "title", feature[0])
            _translated_value(item, "description", feature[1])
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
