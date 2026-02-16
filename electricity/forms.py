from django import forms
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


class Step1Form(forms.Form):
    consultation_type = forms.ChoiceField(
        choices=[
            ("onsite", "On-site Visit"),
            ("video", "Video Call"),
            ("phone", "Phone Call"),
        ],
        widget=forms.RadioSelect,
    )


class Step2Form(forms.Form):
    property_type = forms.ChoiceField(
        choices=[
            ("apartment", "Apartment"),
            ("house", "House"),
            ("office", "Office"),
            ("other", "Other"),
        ],
        widget=forms.RadioSelect,
    )
    property_size = forms.ChoiceField(
        choices=[
            ("small", "Under 100 m2"),
            ("medium", "100-200 m2"),
            ("large", "200-400 m2"),
            ("xlarge", "400+ m2"),
        ],
        widget=forms.Select(attrs={"class": "form-select booking-input"}),
    )
    year_built = forms.CharField(
        required=False, max_length=10, widget=forms.TextInput(attrs={"class": "form-control booking-input"})
    )
    property_type_other = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control booking-input", "placeholder": "Specify property type"}),
    )


class Step3Form(forms.Form):
    services = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("upgrades", "Electrical Upgrades"),
            ("lighting", "Lighting Solutions"),
            ("ev", "EV Charging"),
            ("automation", "Home Automation"),
            ("troubleshooting", "Troubleshooting"),
            ("maintenance", "General Maintenance"),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    urgent = forms.ChoiceField(
        choices=[("no", "No"), ("yes", "Yes")],
        widget=forms.RadioSelect,
    )


class Step4Form(forms.Form):
    project_description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control booking-input", "rows": 6}),
        required=False,
    )


class Step5Form(forms.Form):
    photo = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "booking-file"}))
    video = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"class": "booking-file"}))
    document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"class": "booking-file"}))


class Step6Form(forms.Form):
    contact_type = forms.ChoiceField(
        choices=[("private", "Private"), ("business", "Business")],
        widget=forms.RadioSelect,
    )
    full_name = forms.CharField(max_length=160, widget=forms.TextInput(attrs={"class": "form-control booking-input"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control booking-input"}))
    phone = forms.CharField(required=False, max_length=40, widget=forms.TextInput(attrs={"class": "form-control booking-input"}))
    personal_id = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(attrs={"class": "form-control booking-input", "placeholder": "Personal ID number"}),
    )
    company_name = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={"class": "form-control booking-input", "placeholder": "Company name"}),
    )
    organization_number = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(attrs={"class": "form-control booking-input", "placeholder": "Organization number"}),
    )
    company_address = forms.CharField(
        required=False,
        max_length=220,
        widget=forms.TextInput(attrs={"class": "form-control booking-input", "placeholder": "Company address"}),
    )
    availability_days = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("mon", "Mon"),
            ("tue", "Tue"),
            ("wed", "Wed"),
            ("thu", "Thu"),
            ("fri", "Fri"),
            ("sat", "Sat"),
            ("sun", "Sun"),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    time_window = forms.ChoiceField(
        choices=[
            ("morning", "Morning"),
            ("midday", "Midday"),
            ("afternoon", "Afternoon"),
            ("evening", "Evening"),
        ],
        widget=forms.RadioSelect,
    )


class Step7Form(forms.Form):
    preferred_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control booking-input"}),
    )
    preferred_time_slot = forms.CharField(
        required=False, max_length=60, widget=forms.TextInput(attrs={"class": "form-control booking-input"})
    )


class ZipCheckForm(forms.Form):
    zip_code = forms.CharField(max_length=10)

    def clean_zip_code(self):
        value = self.cleaned_data["zip_code"].strip()
        value = value.replace(" ", "")
        if not value.isdigit() or len(value) != 5:
            raise ValidationError("Please enter a valid Swedish ZIP code (e.g. 114 44).")
        return value


class OutsideAreaRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequestOutsideArea
        fields = ("full_name", "email", "phone", "details")


class AcceptedZipCodeForm(forms.ModelForm):
    class Meta:
        model = AcceptedZipCode
        fields = ("code", "is_active", "note")


class ServiceRequestOutsideAreaAdminForm(forms.ModelForm):
    class Meta:
        model = ServiceRequestOutsideArea
        fields = ("full_name", "email", "phone", "zip_code", "request_type", "details")


class ServicePricingForm(forms.ModelForm):
    class Meta:
        model = ServicePricing
        exclude = ("created_at",)


class ElectricalServiceForm(forms.ModelForm):
    class Meta:
        model = ElectricalService
        fields = (
            "title",
            "short_description",
            "bullet_points",
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
        )
        widgets = {
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "duration_minutes": forms.NumberInput(attrs={"min": "1"}),
        }

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get("price")
        duration = cleaned.get("duration_minutes")
        if price is None or price <= 0:
            self.add_error("price", "Price must be greater than 0.")
        if not duration or duration <= 0:
            self.add_error("duration_minutes", "Duration must be greater than 0.")
        return cleaned


class ConsultationRequestForm(forms.ModelForm):
    class Meta:
        model = ConsultationRequest
        exclude = ("created_at",)


class ConsultationBookingForm(forms.ModelForm):
    class Meta:
        model = ConsultationBooking
        exclude = ("created_at",)


class ServiceBookingForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        exclude = ("created_at",)


class ElectricianBookingForm(forms.ModelForm):
    class Meta:
        model = ElectricianBooking
        exclude = ("created_at",)


class OnCallBookingForm(forms.ModelForm):
    class Meta:
        model = OnCallBooking
        exclude = ("created_at",)


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        exclude = ("created_at",)


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        exclude = ("created_at",)




class ProviderShiftForm(forms.ModelForm):
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

class ProviderProfileForm(forms.ModelForm):
    class Meta:
        model = ProviderProfile
        fields = "__all__"


class ProviderAssignForm(forms.ModelForm):
    class Meta:
        model = ConsultationBooking
        fields = ("assigned_provider",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get("assigned_provider")
        if field:
            field.label_from_instance = lambda obj: f"{obj.display_name} - {obj.availability_status}"


class ServiceBookingAssignForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        fields = ("assigned_provider",)


class OnCallBookingAssignForm(forms.ModelForm):
    class Meta:
        model = OnCallBooking
        fields = ("assigned_provider",)


class ElectricianBookingAssignForm(forms.ModelForm):
    class Meta:
        model = ElectricianBooking
        fields = ("assigned_provider",)


class FAQEntryForm(forms.ModelForm):
    class Meta:
        model = FAQEntry
        fields = ("question", "answer", "is_active", "order")


class BookingStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = BookingStatusUpdate
        fields = ("status", "note")


class ServiceBookingStatusUpdateForm(forms.ModelForm):
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
