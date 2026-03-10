import json
import re
from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm
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
    ElectricalService,
    ElectricianBooking,
    FAQEntry,
    OnCallBooking,
    ProviderProfile,
    ProviderShift,
    ServiceRequestOutsideArea,
    ServiceBooking,
    ServicePricing,
    SupportTicket,
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

    def clean(self):
        cleaned_data = super().clean()
        for field_name in getattr(self, "_json_field_names", []):
            raw_value = cleaned_data.get(field_name)
            if isinstance(raw_value, str):
                cleaned_data[field_name] = self._parse_json_value(field_name, raw_value)
        return cleaned_data

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
                "placeholder": _("Personal ID number"),
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


class Step7Form(forms.Form):
    preferred_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control booking-input"}),
    )
    preferred_time = forms.CharField(
        required=False,
        max_length=5,
        widget=forms.TextInput(
            attrs={
                "class": "form-control booking-input time-slot-input",
                "placeholder": "00:00",
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
    )
    preferred_meridiem = forms.ChoiceField(
        required=False,
        choices=[("AM", "AM"), ("PM", "PM")],
        widget=forms.Select(attrs={"class": "booking-input time-slot-meridiem"}),
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
        fields = _translated_fields("title", "short_description", "bullet_points") + [
            "icon",
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


class CustomerProfileForm(HumanizedJSONModelForm):
    class Meta:
        model = CustomerProfile
        exclude = ("created_at",)




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
