import json
import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import (
    AcceptedZipCode,
    AdminNotification,
    BookingStatusUpdate,
    ServiceBookingStatusUpdate,
    ConsultationBooking,
    ConsultationRequest,
    CustomerProfile,
    Invoice,
    InvoiceLine,
    ElectricalService,
    ElectricianBooking,
    FAQEntry,
    OnCallBooking,
    ProviderProfile,
    ProviderShift,
    ServiceCategoryFAQ,
    ServiceCategoryContentBlock,
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
    ServiceRequestOutsideArea,
    ServiceBooking,
    ServicePricing,
    SupportTicket,
    CustomerFeedback,
)
from . import translation  # noqa: F401


def _translated_fields(*base_fields):
    languages = getattr(settings, "MODELTRANSLATION_LANGUAGES", None)
    if not languages:
        languages = [code for code, _ in settings.LANGUAGES]
    fields = []
    for base in base_fields:
        for lang in languages:
            fields.append(f"{base}_{lang}")
    return fields


class UsernameOrEmailPasswordResetForm(PasswordResetForm):
    email = forms.CharField(label=_("Email or username"))

    def clean_email(self):
        value = self.cleaned_data["email"].strip()
        if not value or "@" in value:
            return value

        user = User.objects.filter(username__iexact=value).first()
        if not user:
            return value
        if not user.email:
            raise ValidationError(_("This account does not have an email address configured for password reset."))
        return user.email


class HumanizedJSONModelForm(forms.ModelForm):
    JSON_TEXTAREA_ROWS = 4
    JSON_LABEL_MAPS = {
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._json_field_names = []
        model = getattr(self.Meta, "model", None)
        if not model:
            return

        for model_field in model._meta.fields:
            if model_field.get_internal_type() != "JSONField" or model_field.name not in self.fields:
                continue

            self._json_field_names.append(model_field.name)
            existing_field = self.fields[model_field.name]
            self.fields[model_field.name] = forms.CharField(
                required=not model_field.blank,
                label=existing_field.label,
                help_text=_("Enter one item per line."),
                widget=forms.Textarea(
                    attrs={
                        "class": "form-control",
                        "rows": self.JSON_TEXTAREA_ROWS,
                    }
                ),
            )
            if not self.is_bound:
                self.initial[model_field.name] = self._format_json_value(
                    model_field.name,
                    getattr(self.instance, model_field.name, None),
                )
        self._require_default_translation_fields(model)

    def clean(self):
        cleaned_data = super().clean()
        for field_name in getattr(self, "_json_field_names", []):
            raw_value = cleaned_data.get(field_name)
            if isinstance(raw_value, str):
                cleaned_data[field_name] = self._parse_json_value(field_name, raw_value)
        return cleaned_data

    def _require_default_translation_fields(self, model):
        default_language = getattr(settings, "MODELTRANSLATION_DEFAULT_LANGUAGE", "")
        if not default_language:
            return

        for field_name, field in self.fields.items():
            suffix = f"_{default_language}"
            if not field_name.endswith(suffix):
                continue

            base_name = field_name[: -len(suffix)]
            try:
                model_field = model._meta.get_field(base_name)
            except Exception:
                continue

            field.required = not getattr(model_field, "blank", True)

    def _format_json_value(self, field_name, value):
        if value in (None, "", [], {}):
            return ""
        if isinstance(value, list):
            return "\n".join(self._format_json_item(field_name, item) for item in value if item not in (None, ""))
        if isinstance(value, dict):
            return "\n".join(f"{key}: {val}" for key, val in value.items())
        return str(value)

    def _format_json_item(self, field_name, item):
        if field_name == "services":
            service_map = self._service_title_map([item])
            label = service_map.get(str(item))
            if label:
                return label
        label_map = self.JSON_LABEL_MAPS.get(field_name, {})
        return str(label_map.get(item, item))

    def _parse_json_value(self, field_name, raw_value):
        text = (raw_value or "").strip()
        if not text:
            return []

        if text[0] in "[{":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return parsed

        lines = [line.strip(" ,") for line in text.splitlines() if line.strip(" ,")]
        if len(lines) <= 1 and "," in text:
            lines = [part.strip(" ,") for part in text.split(",") if part.strip(" ,")]

        if field_name == "services":
            return self._parse_service_items(lines)
        return lines

    def _service_title_map(self, values):
        service_ids = []
        for value in values:
            if str(value).isdigit():
                service_ids.append(int(value))
        if not service_ids:
            return {}
        return {
            str(service.id): service.title
            for service in ElectricalService.objects.filter(id__in=service_ids)
        }

    def _parse_service_items(self, items):
        services = ElectricalService.objects.all().only("id", "title")
        title_map = {service.title.strip().lower(): str(service.id) for service in services if service.title}
        parsed = []
        for item in items:
            match = re.search(r"\b(?:id|service)\s*[:#-]?\s*(\d+)\b", item, flags=re.IGNORECASE)
            if match:
                parsed.append(match.group(1))
                continue
            if item.isdigit():
                parsed.append(item)
                continue
            mapped = title_map.get(item.strip().lower())
            parsed.append(mapped or item)
        return parsed


class Step1Form(forms.Form):
    consultation_type = forms.ChoiceField(
        choices=[
            ("onsite", _("On-site Visit")),
            ("video", _("Video Call")),
            ("phone", _("Phone Call")),
        ],
        widget=forms.RadioSelect,
    )


class Step2Form(forms.Form):
    property_type = forms.ChoiceField(
        choices=[
            ("apartment", _("Apartment")),
            ("house", _("House")),
            ("office", _("Office")),
            ("other", _("Other")),
        ],
        widget=forms.RadioSelect,
    )
    property_size = forms.ChoiceField(
        choices=[
            ("small", _("Under 100 m2")),
            ("medium", _("100-200 m2")),
            ("large", _("200-400 m2")),
            ("xlarge", _("400+ m2")),
        ],
        widget=forms.Select(attrs={"class": "booking-input"}),
    )
    year_built = forms.CharField(
        required=False, max_length=10, widget=forms.TextInput(attrs={"class": "form-control booking-input"})
    )
    property_type_other = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control booking-input", "placeholder": _("Specify property type")}),
    )


class Step3Form(forms.Form):
    services = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("upgrades", _("Electrical Upgrades")),
            ("lighting", _("Lighting Solutions")),
            ("ev", _("EV Charging")),
            ("automation", _("Home Automation")),
            ("troubleshooting", _("Troubleshooting")),
            ("maintenance", _("General Maintenance")),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    urgent = forms.ChoiceField(
        choices=[("no", _("No")), ("yes", _("Yes"))],
        widget=forms.RadioSelect,
    )


class Step4Form(forms.Form):
    project_description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control booking-input", "rows": 6}),
        required=False,
    )


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)]


class Step5Form(forms.Form):
    photo = MultipleFileField(
        required=False,
        widget=MultipleFileInput(
            attrs={"class": "booking-file", "accept": "image/jpeg,image/png,image/webp"}
        ),
    )
    video = MultipleFileField(
        required=False,
        widget=MultipleFileInput(
            attrs={"class": "booking-file", "accept": "video/mp4,video/quicktime,video/webm"}
        ),
    )
    document = MultipleFileField(
        required=False,
        widget=MultipleFileInput(
            attrs={
                "class": "booking-file",
                "accept": ".pdf,.doc,.docx,.txt,.xls,.xlsx,.ppt,.pptx",
            }
        ),
    )


class Step6Form(forms.Form):
    contact_type = forms.ChoiceField(
        choices=[("private", _("Private")), ("business", _("Business"))],
        widget=forms.RadioSelect,
    )
    full_name = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={"class": "form-control booking-input"}),
    )
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control booking-input"}))
    phone = forms.CharField(required=False, max_length=40, widget=forms.TextInput(attrs={"class": "form-control booking-input"}))
    personal_id = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(
            attrs={
                "class": "form-control booking-input",
                "placeholder": "yyyymmdd-xxxx",
                "inputmode": "numeric",
                "pattern": r"\d{8}-\d{4}",
                "data-contact-field": "private",
            }
        ),
    )
    company_name = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(
            attrs={
                "class": "form-control booking-input",
                "placeholder": _("Company name"),
                "data-contact-field": "business",
            }
        ),
    )
    organization_number = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(
            attrs={
                "class": "form-control booking-input",
                "placeholder": _("Organization number"),
                "data-contact-field": "business",
            }
        ),
    )
    company_address = forms.CharField(
        required=False,
        max_length=220,
        widget=forms.TextInput(
            attrs={
                "class": "form-control booking-input",
                "placeholder": _("Company address"),
                "data-contact-field": "business",
            }
        ),
    )
    availability_days = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("mon", _("Mon")),
            ("tue", _("Tue")),
            ("wed", _("Wed")),
            ("thu", _("Thu")),
            ("fri", _("Fri")),
            ("sat", _("Sat")),
            ("sun", _("Sun")),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    time_window = forms.ChoiceField(
        required=False,
        choices=[
            ("morning", _("Morning")),
            ("midday", _("Midday")),
            ("afternoon", _("Afternoon")),
            ("evening", _("Evening")),
        ],
        widget=forms.RadioSelect,
    )

    def clean_personal_id(self):
        value = (self.cleaned_data.get("personal_id") or "").strip()
        if not value:
            return value
        if not re.fullmatch(r"\d{8}-\d{4}", value):
            raise ValidationError(_("Please enter your personal ID in the format yyyymmdd-xxxx."))
        return value


class Step7Form(forms.Form):
    preferred_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control booking-input"}),
    )
    preferred_time = forms.CharField(
        required=False,
        max_length=5,
        widget=forms.TimeInput(
            attrs={
                "type": "time",
                "class": "form-control booking-input time-slot-input",
                "placeholder": "00:00",
                "step": "60",
                "autocomplete": "off",
            }
        ),
    )


class ZipCheckForm(forms.Form):
    zip_code = forms.CharField(max_length=10)

    def clean_zip_code(self):
        value = self.cleaned_data["zip_code"].strip()
        value = re.sub(r"\s+", "", value)
        if not value.isdigit() or len(value) != 5:
            raise ValidationError(_("Please enter a valid Swedish ZIP code (e.g. 114 44)."))
        return value


class OutsideAreaRequestForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceRequestOutsideArea
        fields = ("full_name", "email", "phone", "details")


class AcceptedZipCodeForm(HumanizedJSONModelForm):
    class Meta:
        model = AcceptedZipCode
        fields = ("code", "is_active", "note")


class ServiceRequestOutsideAreaAdminForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceRequestOutsideArea
        fields = ("full_name", "email", "phone", "zip_code", "request_type", "details")


class ServicePricingForm(HumanizedJSONModelForm):
    class Meta:
        model = ServicePricing
        fields = _translated_fields("name") + [
            "labor_rate",
            "transport_fee",
            "hourly_rate_electrician",
            "hourly_rate_emergency",
            "consultation_price",
            "rot_percent",
            "currency",
            "is_active",
        ]


class ElectricalServiceForm(HumanizedJSONModelForm):
    class Meta:
        model = ElectricalService
        fields = _translated_fields("title", "bullet_points") + [
            "icon",
            "price",
            "duration_minutes",
            "service_fee",
            "base_fee",
            "hourly_rate",
            "night_rate",
            "transport_fee",
            "rot_percent",
            "currency",
            "is_active",
            "order",
        ]


class ConsultationRequestForm(HumanizedJSONModelForm):
    class Meta:
        model = ConsultationRequest
        exclude = ("created_at",)


class ConsultationBookingForm(HumanizedJSONModelForm):
    class Meta:
        model = ConsultationBooking
        exclude = ("created_at",)


class ServiceBookingForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceBooking
        exclude = ("created_at",)


class ElectricianBookingForm(HumanizedJSONModelForm):
    class Meta:
        model = ElectricianBooking
        exclude = ("created_at",)


class OnCallBookingForm(HumanizedJSONModelForm):
    class Meta:
        model = OnCallBooking
        exclude = ("created_at",)


class SupportTicketForm(HumanizedJSONModelForm):
    class Meta:
        model = SupportTicket
        exclude = ("created_at",)


class CustomerFeedbackForm(HumanizedJSONModelForm):
    class Meta:
        model = CustomerFeedback
        fields = ("full_name", "email", "location", "rating", "message")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].widget.attrs.update({"class": "form-control"})
        self.fields["email"].widget.attrs.update({"class": "form-control"})
        self.fields["location"].widget.attrs.update({"class": "form-control"})
        self.fields["rating"].widget = forms.Select(
            choices=[(5, "5 / 5"), (4, "4 / 5"), (3, "3 / 5"), (2, "2 / 5"), (1, "1 / 5")],
            attrs={"class": "form-control"},
        )
        self.fields["message"].widget.attrs.update({"class": "form-control", "rows": 6})


class CustomerFeedbackAdminForm(HumanizedJSONModelForm):
    class Meta:
        model = CustomerFeedback
        fields = ("full_name", "email", "location", "rating", "message", "is_approved")


class CustomerProfileForm(HumanizedJSONModelForm):
    class Meta:
        model = CustomerProfile
        exclude = ("created_at",)


class InvoiceForm(HumanizedJSONModelForm):
    class Meta:
        model = Invoice
        exclude = (
            "subtotal_ex_vat", "discount_total", "vat_total", "rot_total",
            "total_inc_vat", "amount_due", "sent_at", "created_at", "updated_at",
            "consultation_booking", "service_booking", "electrician_booking", "on_call_booking",
            "status",
        )
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "customer_message": forms.Textarea(attrs={"rows": 3}),
            "payment_instructions": forms.Textarea(attrs={"rows": 3}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
            "additional_terms": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("recipient_email"):
            self.add_error("recipient_email", "A recipient email is required to send the invoice.")
        if cleaned.get("due_date") and cleaned.get("invoice_date") and cleaned["due_date"] < cleaned["invoice_date"]:
            self.add_error("due_date", "Due date cannot be earlier than invoice date.")
        if cleaned.get("rot_enabled"):
            if not cleaned.get("rot_personal_number"):
                self.add_error("rot_personal_number", "Personal number is required for ROT.")
            if not cleaned.get("rot_property_designation"):
                self.add_error("rot_property_designation", "Property designation is required for ROT.")
        if cleaned.get("invoice_type") == Invoice.InvoiceType.PART:
            if not cleaned.get("part_number"):
                self.add_error("part_number", "Part number is required for a part invoice.")
            if not cleaned.get("part_total"):
                self.add_error("part_total", "Total number of parts is required for a part invoice.")
            if cleaned.get("part_number") and cleaned.get("part_total") and cleaned["part_number"] > cleaned["part_total"]:
                self.add_error("part_number", "Part number cannot be greater than total parts.")
        return cleaned


class InvoiceLineForm(HumanizedJSONModelForm):
    def has_changed(self):
        """Do not treat the defaults in a blank extra row as user input."""
        if not self.is_bound or self.instance.pk:
            return super().has_changed()

        value = lambda name: str(self.data.get(self.add_prefix(name), "")).strip()
        blank_defaults = {
            "description": "",
            "category": InvoiceLine.Category.LABOUR,
            "quantity": "1",
            "unit": "fixed price",
            "unit_price_ex_vat": "0",
            "discount_type": "none",
            "discount_value": "0",
            "vat_percent": "25",
            "rot_eligible": "",
        }
        for name, default in blank_defaults.items():
            submitted = value(name)
            if name in {"quantity", "unit_price_ex_vat", "discount_value", "vat_percent"}:
                try:
                    if Decimal(submitted or "0") != Decimal(default):
                        return True
                except InvalidOperation:
                    return True
            elif submitted != default:
                return True
        return False

    class Meta:
        model = InvoiceLine
        exclude = ("invoice", "order")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


InvoiceLineFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)




class ProviderShiftForm(HumanizedJSONModelForm):
    WEEKDAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    class Meta:
        model = ProviderShift
        fields = ("provider", "weekday", "start_time", "end_time")
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["weekday"].widget = forms.Select(choices=self.WEEKDAY_CHOICES)

class ProviderProfileForm(HumanizedJSONModelForm):
    class Meta:
        model = ProviderProfile
        fields = "__all__"


class ProviderAssignForm(HumanizedJSONModelForm):
    class Meta:
        model = ConsultationBooking
        fields = ("assigned_provider",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get("assigned_provider")
        if field:
            field.label_from_instance = lambda obj: f"{obj.display_name} - {obj.availability_status}"


class ServiceBookingAssignForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceBooking
        fields = ("assigned_provider",)


class OnCallBookingAssignForm(HumanizedJSONModelForm):
    class Meta:
        model = OnCallBooking
        fields = ("assigned_provider",)


class ElectricianBookingAssignForm(HumanizedJSONModelForm):
    class Meta:
        model = ElectricianBooking
        fields = ("assigned_provider",)


class FAQEntryForm(HumanizedJSONModelForm):
    class Meta:
        model = FAQEntry
        fields = _translated_fields("question", "answer") + ["is_active", "order"]


class ServiceCategoryPageForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceCategoryPage
        fields = _translated_fields(
            "name",
            "nav_label",
            "teaser",
            "hero_eyebrow",
            "hero_title",
            "hero_highlight",
            "hero_description",
            "hero_card_title",
            "hero_card_lines",
            "notice_text",
            "primary_cta_label",
            "secondary_cta_label",
            "specs_title",
            "specs_subtitle",
            "spec_col_1",
            "spec_col_2",
            "spec_col_3",
            "spec_col_4",
            "spec_col_5",
            "spec_col_6",
            "spec_col_7",
            "faq_title",
            "faq_subtitle",
            "cta_title",
            "cta_description",
            "cta_primary_label",
            "cta_secondary_label",
        ) + [
            "theme",
            "slug",
            "hero_image",
            "primary_cta_url",
            "secondary_cta_url",
            "cta_image",
            "cta_primary_url",
            "cta_secondary_url",
            "is_active",
            "order",
        ]


class ServiceCategorySectionForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceCategorySection
        fields = ["page", "kind"] + _translated_fields("title", "subtitle", "description") + ["order"]


class ServiceCategoryContentBlockForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceCategoryContentBlock
        fields = ["page", "target_service_page", "layout"] + _translated_fields(
            "eyebrow",
            "title",
            "subtitle",
            "body",
            "secondary_body",
            "image_alt",
            "badge",
            "list_title",
            "list_lines",
            "stat_label",
            "stat_value",
            "cta_label",
        ) + [
            "image",
            "cta_url",
            "is_active",
            "order",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["page"].label = "Parent Category"
        self.fields["page"].help_text = "Choose the main parent section first."
        self.fields["target_service_page"].label = "Target Service Page"
        self.fields["target_service_page"].help_text = "Optional. If selected, this block appears only on that inner service page. If left empty, it appears on the main category page."
        pages_qs = ServiceDetailPage.objects.select_related("parent_category").order_by(
            "parent_category__order", "menu_group", "order", "name"
        )
        self.fields["target_service_page"].queryset = pages_qs

        selected_parent_id = ""
        if self.is_bound:
            selected_parent_id = str(self.data.get("page") or "")
        elif getattr(self.instance, "pk", None):
            selected_parent_id = str(getattr(self.instance, "page_id", "") or "")
        elif self.initial.get("page"):
            selected_parent_id = str(self.initial.get("page") or "")

        self.category_service_page_pairs = json.dumps(
            {str(page.pk): str(page.parent_category_id) for page in pages_qs}
        )
        self.selected_parent_category_id = selected_parent_id


class ServiceCategoryItemForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceCategoryItem
        fields = ["section"] + _translated_fields(
            "badge",
            "title",
            "subtitle",
            "description",
            "price_text",
            "price_note",
            "meta_lines",
            "included_title",
            "included_lines",
            "excluded_title",
            "excluded_lines",
            "cta_label",
        ) + [
            "image",
            "cta_url",
            "is_featured",
            "order",
        ]


class ServiceCategorySpecRowForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceCategorySpecRow
        fields = ["page"] + _translated_fields("label", "value_1", "value_2", "value_3", "value_4", "value_5", "value_6") + ["order"]


class ServiceCategoryFAQForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceCategoryFAQ
        fields = ["page"] + _translated_fields("question", "answer") + ["is_active", "order"]


class ServiceDetailPageForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceDetailPage
        fields = ["parent_category"] + _translated_fields(
            "menu_group",
            "name",
            "nav_label",
            "teaser",
            "hero_eyebrow",
            "hero_title",
            "hero_highlight",
            "hero_description",
            "hero_card_title",
            "hero_card_lines",
            "notice_text",
            "primary_cta_label",
            "secondary_cta_label",
            "specs_title",
            "specs_subtitle",
            "spec_col_1",
            "spec_col_2",
            "spec_col_3",
            "spec_col_4",
            "spec_col_5",
            "spec_col_6",
            "spec_col_7",
            "faq_title",
            "faq_subtitle",
            "cta_title",
            "cta_description",
            "cta_primary_label",
            "cta_secondary_label",
        ) + [
            "slug",
            "hero_image",
            "primary_cta_url",
            "secondary_cta_url",
            "cta_image",
            "cta_primary_url",
            "cta_secondary_url",
            "is_active",
            "order",
        ]


class ServiceDetailSectionForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceDetailSection
        fields = ["page", "kind"] + _translated_fields("title", "subtitle", "description") + ["order"]


class ServiceDetailContentBlockForm(HumanizedJSONModelForm):
    parent_category_filter = forms.ModelChoiceField(
        queryset=ServiceCategoryPage.objects.all().order_by("order", "name"),
        required=False,
        label="Parent Category",
        help_text="Choose the parent category first, then select one of its inner service pages below.",
    )

    class Meta:
        model = ServiceDetailContentBlock
        fields = ["page", "layout"] + _translated_fields(
            "eyebrow",
            "title",
            "subtitle",
            "body",
            "secondary_body",
            "image_alt",
            "badge",
            "list_title",
            "list_lines",
            "stat_label",
            "stat_value",
            "cta_label",
        ) + [
            "image",
            "cta_url",
            "is_active",
            "order",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            ["parent_category_filter", "page", "layout"]
            + [name for name in self.fields.keys() if name not in {"parent_category_filter", "page", "layout"}]
        )
        pages_qs = ServiceDetailPage.objects.select_related("parent_category").order_by(
            "parent_category__order", "menu_group", "order", "name"
        )
        self.fields["page"].queryset = pages_qs
        self.fields["page"].label = "Service Page"
        self.fields["page"].help_text = "This block appears only on the selected inner service page."

        selected_parent_id = ""
        if self.is_bound:
            selected_parent_id = str(self.data.get("parent_category_filter") or "")
        elif getattr(self.instance, "pk", None):
            selected_parent_id = str(getattr(self.instance.page, "parent_category_id", "") or "")
            self.fields["parent_category_filter"].initial = selected_parent_id or None
        elif self.initial.get("page"):
            try:
                selected_page = pages_qs.get(pk=self.initial["page"])
                selected_parent_id = str(selected_page.parent_category_id or "")
                self.fields["parent_category_filter"].initial = selected_parent_id or None
            except ServiceDetailPage.DoesNotExist:
                selected_parent_id = ""

        self.service_page_parent_pairs = json.dumps(
            {str(page.pk): str(page.parent_category_id) for page in pages_qs}
        )
        self.selected_parent_category_id = selected_parent_id


class ServiceDetailItemForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceDetailItem
        fields = ["section"] + _translated_fields(
            "badge",
            "title",
            "subtitle",
            "description",
            "price_text",
            "price_note",
            "meta_lines",
            "included_title",
            "included_lines",
            "excluded_title",
            "excluded_lines",
            "cta_label",
        ) + [
            "image",
            "cta_url",
            "is_featured",
            "order",
        ]


class ServiceDetailSpecRowForm(HumanizedJSONModelForm):
    parent_category_filter = forms.ModelChoiceField(
        queryset=ServiceCategoryPage.objects.all().order_by("order", "name"),
        required=False,
        label="Parent Category",
        help_text="Choose the parent category first, then select the exact inner service page for this spec table row.",
    )

    class Meta:
        model = ServiceDetailSpecRow
        fields = ["page"] + _translated_fields("label", "value_1", "value_2", "value_3", "value_4", "value_5", "value_6") + ["order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            ["parent_category_filter", "page"]
            + [name for name in self.fields.keys() if name not in {"parent_category_filter", "page"}]
        )
        pages_qs = ServiceDetailPage.objects.select_related("parent_category").order_by(
            "parent_category__order", "menu_group", "order", "name"
        )
        self.fields["page"].queryset = pages_qs
        self.fields["page"].label = "Service Page"
        self.fields["page"].help_text = "This spec row will appear only on the selected inner service page."

        selected_parent_id = ""
        if self.is_bound:
            selected_parent_id = str(self.data.get("parent_category_filter") or "")
        elif getattr(self.instance, "pk", None):
            selected_parent_id = str(getattr(self.instance.page, "parent_category_id", "") or "")
            self.fields["parent_category_filter"].initial = selected_parent_id or None
        elif self.initial.get("page"):
            try:
                selected_page = pages_qs.get(pk=self.initial["page"])
                selected_parent_id = str(selected_page.parent_category_id or "")
                self.fields["parent_category_filter"].initial = selected_parent_id or None
            except ServiceDetailPage.DoesNotExist:
                selected_parent_id = ""

        self.service_page_parent_pairs = json.dumps(
            {str(page.pk): str(page.parent_category_id) for page in pages_qs}
        )
        self.selected_parent_category_id = selected_parent_id


class ServiceDetailFAQForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceDetailFAQ
        fields = ["page"] + _translated_fields("question", "answer") + ["is_active", "order"]


class BookingStatusUpdateForm(HumanizedJSONModelForm):
    class Meta:
        model = BookingStatusUpdate
        fields = ("status", "note")


class ServiceBookingStatusUpdateForm(HumanizedJSONModelForm):
    class Meta:
        model = ServiceBookingStatusUpdate
        fields = ("status", "note")


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("username", "email", "is_staff", "is_active")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            raise ValidationError("Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    new_password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ("username", "email", "is_staff", "is_active")

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get("new_password")
        if new_password:
            user.set_password(new_password)
        if commit:
            user.save()
        return user


class SignupForm(UserCreationForm):
    account_type = forms.ChoiceField(
        choices=[("private", "Private"), ("business", "Business")],
        widget=forms.RadioSelect,
    )
    full_name = forms.CharField(max_length=160)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)
    street_address = forms.CharField(max_length=200, required=False)
    city = forms.CharField(max_length=80, required=False)
    postal_code = forms.CharField(max_length=20, required=False)
    country = forms.CharField(max_length=60, initial="Germany")
    property_type = forms.ChoiceField(
        required=False,
        choices=[
            ("apartment", "Apartment"),
            ("house", "House"),
            ("office", "Office"),
            ("other", "Other"),
        ],
        widget=forms.Select,
    )
    interests = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("upgrades", "Electrical upgrades"),
            ("lighting", "Lighting solutions"),
            ("ev", "EV charging"),
            ("automation", "Home automation"),
            ("maintenance", "Maintenance"),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    personal_id = forms.CharField(max_length=40, required=False)
    company_name = forms.CharField(max_length=160, required=False)
    organization_number = forms.CharField(max_length=40, required=False)
    company_address = forms.CharField(max_length=220, required=False)
    accepted_terms = forms.BooleanField(required=True)
    accepted_privacy = forms.BooleanField(required=True)
    marketing_opt_in = forms.BooleanField(required=False)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    def clean(self):
        cleaned = super().clean()
        account_type = cleaned.get("account_type")
        if account_type == "private" and not cleaned.get("personal_id"):
            self.add_error("personal_id", "Personal ID is required for private accounts.")
        if account_type == "business":
            if not cleaned.get("company_name"):
                self.add_error("company_name", "Company name is required.")
            if not cleaned.get("organization_number"):
                self.add_error("organization_number", "Organization number is required.")
            if not cleaned.get("company_address"):
                self.add_error("company_address", "Company address is required.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            CustomerProfile.objects.create(
                user=user,
                account_type=self.cleaned_data["account_type"],
                full_name=self.cleaned_data["full_name"],
                email=self.cleaned_data.get("email", ""),
                phone=self.cleaned_data.get("phone", ""),
                street_address=self.cleaned_data.get("street_address", ""),
                city=self.cleaned_data.get("city", ""),
                postal_code=self.cleaned_data.get("postal_code", ""),
                country=self.cleaned_data.get("country", "Germany"),
                property_type=self.cleaned_data.get("property_type", ""),
                interests=self.cleaned_data.get("interests", []),
                personal_id=self.cleaned_data.get("personal_id", ""),
                company_name=self.cleaned_data.get("company_name", ""),
                organization_number=self.cleaned_data.get("organization_number", ""),
                company_address=self.cleaned_data.get("company_address", ""),
                accepted_terms=self.cleaned_data.get("accepted_terms", False),
                accepted_privacy=self.cleaned_data.get("accepted_privacy", False),
                marketing_opt_in=self.cleaned_data.get("marketing_opt_in", False),
            )
        return user
