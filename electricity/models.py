import datetime
import re
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone


class ElectricalService(models.Model):
    title = models.CharField(max_length=120)
    short_description = models.TextField(blank=True, default="")
    bullet_points = models.TextField(blank=True, default="")
    icon = models.ImageField(upload_to='electricity/services/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=0, blank=True, null=True)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    night_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rot_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    currency = models.CharField(max_length=10, default="SEK")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]

    @property
    def is_bookable(self):
        return self.is_active and (self.price or 0) > 0 and (self.duration_minutes or 0) > 0

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ConsultationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DONE = "done", "Done"
        CANCELED = "canceled", "Canceled"

    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40)
    email = models.EmailField(blank=True)
    service = models.ForeignKey(
        ElectricalService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultation_requests",
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class ContactInquiry(models.Model):
    class InquiryType(models.TextChoices):
        NEW_BOOKING = "new_booking", "New service bookings"
        CONSULTATION = "consultation", "Professional consultations"
        TECH_SUPPORT = "tech_support", "Technical questions & support"

    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=200, blank=True)
    request_type = models.CharField(max_length=80, blank=True)
    inquiry_type = models.CharField(max_length=40, choices=InquiryType.choices)
    message = models.TextField()
    consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_inquiry_type_display()})"


class ServiceBooking(models.Model):
    class AccountType(models.TextChoices):
        PRIVATE = "private", "Private Customer"
        BUSINESS = "business", "Business / BRF"

    class BillingType(models.TextChoices):
        PRIVATE = "private", "Private (Personal ID)"
        BUSINESS = "business", "Business (Org Number)"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SCHEDULED = "scheduled", "Scheduled"
        ON_THE_WAY = "on_the_way", "On the way"
        STARTED = "started", "Started"
        PAUSED = "paused", "Paused"
        RESUMED = "resumed", "Resumed"
        COMPLETED = "completed", "Completed"
        NOT_AVAILABLE = "not_available", "Arrived but customer not available"
        CANCELED = "canceled", "Canceled"

    class PricingType(models.TextChoices):
        HOURLY = "hourly", "Hourly electrician"
        FIXED = "fixed", "Fixed service price"

    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)

    street_address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=60, default="Sweden")

    property_type = models.CharField(max_length=60, blank=True)
    year_built = models.CharField(max_length=20, blank=True)
    property_size = models.CharField(max_length=40, blank=True)
    system_upgraded = models.BooleanField(default=False)

    services = models.JSONField(default=list, blank=True)
    work_description = models.TextField(blank=True)
    urgent = models.BooleanField(default=False)

    pricing_type = models.CharField(
        max_length=20, choices=PricingType.choices, default=PricingType.FIXED
    )
    hourly_hours = models.PositiveIntegerField(default=1)
    hourly_rate_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fixed_services_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    preferred_date = models.DateField(blank=True, null=True)
    preferred_time_slot = models.CharField(max_length=60, blank=True)
    alt_date = models.DateField(blank=True, null=True)
    alt_time_slot = models.CharField(max_length=60, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    labor_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    service_fee_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    night_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="SEK")
    promo_code = models.CharField(max_length=40, blank=True)
    rot_deduction = models.BooleanField(default=False)
    estimated_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    billing_type = models.CharField(max_length=20, choices=BillingType.choices, blank=True)
    personal_id = models.CharField(max_length=40, blank=True)
    organization_number = models.CharField(max_length=40, blank=True)
    company_name = models.CharField(max_length=160, blank=True)

    brf_property = models.BooleanField(default=False)
    brf_name = models.CharField(max_length=120, blank=True)
    apartment_number = models.CharField(max_length=20, blank=True)

    uploads = models.JSONField(default=list, blank=True)

    assigned_provider = models.ForeignKey(
        "ProviderProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_service_bookings",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        errors = {}
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            errors["end_at"] = "End time must be after the start time."

        if self.assigned_provider and self.start_at and self.end_at:
            overlaps = ServiceBooking.objects.filter(
                assigned_provider=self.assigned_provider,
            ).exclude(
                status__in=[ServiceBooking.Status.COMPLETED, ServiceBooking.Status.CANCELED]
            ).exclude(
                start_at__isnull=True
            ).exclude(
                end_at__isnull=True
            ).filter(
                start_at__lt=self.end_at,
                end_at__gt=self.start_at,
            )
            if self.pk:
                overlaps = overlaps.exclude(pk=self.pk)
            if overlaps.exists():
                errors["assigned_provider"] = "Provider has an overlapping booking for this time."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class ElectricianBooking(models.Model):
    class CustomerType(models.TextChoices):
        PRIVATE = "private", "Private Customer"
        BUSINESS = "business", "Business / Organization"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    customer_type = models.CharField(max_length=20, choices=CustomerType.choices)
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)

    street_address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)

    property_type = models.CharField(max_length=60, blank=True)
    work_description = models.TextField(blank=True)
    access_notes = models.CharField(max_length=200, blank=True)
    parking_info = models.CharField(max_length=200, blank=True)
    additional_notes = models.TextField(blank=True)

    preferred_date = models.DateField(blank=True, null=True)
    arrival_window = models.CharField(max_length=80, blank=True)

    hours = models.PositiveIntegerField(default=1)
    hourly_rate_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_fee_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rot_requested = models.BooleanField(default=False)
    rot_percent_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    estimated_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="SEK")

    assigned_provider = models.ForeignKey(
        "ProviderProfile",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="assigned_electrician_bookings",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class FAQEntry(models.Model):
    question = models.CharField(max_length=240)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.question


class ServiceCategoryPage(models.Model):
    class Theme(models.TextChoices):
        ELECTRICAL = "electrical", "Electrical Installations"
        SMART = "smart", "Smart Home & EV Charging"
        LIGHTING = "lighting", "Lighting & Appliances"

    theme = models.CharField(max_length=20, choices=Theme.choices, unique=True)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=140)
    nav_label = models.CharField(max_length=80, blank=True)
    teaser = models.TextField(blank=True)
    hero_eyebrow = models.CharField(max_length=120, blank=True)
    hero_title = models.CharField(max_length=160)
    hero_highlight = models.CharField(max_length=160, blank=True)
    hero_description = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="electricity/category_pages/heroes/", blank=True, null=True)
    hero_card_title = models.CharField(max_length=120, blank=True)
    hero_card_lines = models.TextField(blank=True, default="")
    notice_text = models.CharField(max_length=255, blank=True)
    primary_cta_label = models.CharField(max_length=80, blank=True)
    primary_cta_url = models.CharField(max_length=240, blank=True)
    secondary_cta_label = models.CharField(max_length=80, blank=True)
    secondary_cta_url = models.CharField(max_length=240, blank=True)
    specs_title = models.CharField(max_length=160, blank=True)
    specs_subtitle = models.CharField(max_length=200, blank=True)
    spec_col_1 = models.CharField(max_length=80, blank=True)
    spec_col_2 = models.CharField(max_length=80, blank=True)
    spec_col_3 = models.CharField(max_length=80, blank=True)
    spec_col_4 = models.CharField(max_length=80, blank=True)
    spec_col_5 = models.CharField(max_length=80, blank=True)
    spec_col_6 = models.CharField(max_length=80, blank=True)
    spec_col_7 = models.CharField(max_length=80, blank=True)
    faq_title = models.CharField(max_length=160, blank=True)
    faq_subtitle = models.CharField(max_length=200, blank=True)
    cta_title = models.CharField(max_length=160, blank=True)
    cta_description = models.TextField(blank=True)
    cta_image = models.ImageField(upload_to="electricity/category_pages/cta/", blank=True, null=True)
    cta_primary_label = models.CharField(max_length=80, blank=True)
    cta_primary_url = models.CharField(max_length=240, blank=True)
    cta_secondary_label = models.CharField(max_length=80, blank=True)
    cta_secondary_url = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class ServiceCategorySection(models.Model):
    class Kind(models.TextChoices):
        PRODUCTS = "products", "Products"
        FEATURES = "features", "Feature Cards"
        ACCESSORIES = "accessories", "Accessories"

    page = models.ForeignKey(
        ServiceCategoryPage,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PRODUCTS)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.name} - {self.title}"


class ServiceCategoryContentBlock(models.Model):
    class Layout(models.TextChoices):
        TEXT = "text", "Text only"
        SPLIT_IMAGE_RIGHT = "split_image_right", "Text with image right"
        SPLIT_IMAGE_LEFT = "split_image_left", "Text with image left"
        EMPHASIS = "emphasis", "Emphasis band"
        CHECKLIST = "checklist", "Checklist panel"

    page = models.ForeignKey(
        ServiceCategoryPage,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    target_service_page = models.ForeignKey(
        "ServiceDetailPage",
        on_delete=models.CASCADE,
        related_name="category_content_blocks",
        blank=True,
        null=True,
    )
    layout = models.CharField(max_length=24, choices=Layout.choices, default=Layout.TEXT)
    eyebrow = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    secondary_body = models.TextField(blank=True)
    image = models.ImageField(upload_to="electricity/category_pages/blocks/", blank=True, null=True)
    image_alt = models.CharField(max_length=160, blank=True)
    badge = models.CharField(max_length=80, blank=True)
    list_title = models.CharField(max_length=80, blank=True)
    list_lines = models.TextField(blank=True, default="")
    stat_label = models.CharField(max_length=80, blank=True)
    stat_value = models.CharField(max_length=80, blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.name} - {self.title}"


class ServiceCategoryItem(models.Model):
    section = models.ForeignKey(
        ServiceCategorySection,
        on_delete=models.CASCADE,
        related_name="items",
    )
    badge = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="electricity/category_pages/items/", blank=True, null=True)
    price_text = models.CharField(max_length=80, blank=True)
    price_note = models.CharField(max_length=80, blank=True)
    meta_lines = models.TextField(blank=True, default="")
    included_title = models.CharField(max_length=80, blank=True)
    included_lines = models.TextField(blank=True, default="")
    excluded_title = models.CharField(max_length=80, blank=True)
    excluded_lines = models.TextField(blank=True, default="")
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=240, blank=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class ServiceCategorySpecRow(models.Model):
    page = models.ForeignKey(
        ServiceCategoryPage,
        on_delete=models.CASCADE,
        related_name="spec_rows",
    )
    label = models.CharField(max_length=120)
    value_1 = models.CharField(max_length=160, blank=True)
    value_2 = models.CharField(max_length=160, blank=True)
    value_3 = models.CharField(max_length=160, blank=True)
    value_4 = models.CharField(max_length=160, blank=True)
    value_5 = models.CharField(max_length=160, blank=True)
    value_6 = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.name} - {self.label}"


class ServiceCategoryFAQ(models.Model):
    page = models.ForeignKey(
        ServiceCategoryPage,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    question = models.CharField(max_length=240)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.question


class ServiceDetailPage(models.Model):
    parent_category = models.ForeignKey(
        ServiceCategoryPage,
        on_delete=models.CASCADE,
        related_name="service_pages",
    )
    menu_group = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=140)
    nav_label = models.CharField(max_length=80, blank=True)
    teaser = models.TextField(blank=True)
    hero_eyebrow = models.CharField(max_length=120, blank=True)
    hero_title = models.CharField(max_length=160)
    hero_highlight = models.CharField(max_length=160, blank=True)
    hero_description = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="electricity/service_pages/heroes/", blank=True, null=True)
    hero_card_title = models.CharField(max_length=120, blank=True)
    hero_card_lines = models.TextField(blank=True, default="")
    notice_text = models.CharField(max_length=255, blank=True)
    primary_cta_label = models.CharField(max_length=80, blank=True)
    primary_cta_url = models.CharField(max_length=240, blank=True)
    secondary_cta_label = models.CharField(max_length=80, blank=True)
    secondary_cta_url = models.CharField(max_length=240, blank=True)
    specs_title = models.CharField(max_length=160, blank=True)
    specs_subtitle = models.CharField(max_length=200, blank=True)
    spec_col_1 = models.CharField(max_length=80, blank=True)
    spec_col_2 = models.CharField(max_length=80, blank=True)
    spec_col_3 = models.CharField(max_length=80, blank=True)
    spec_col_4 = models.CharField(max_length=80, blank=True)
    spec_col_5 = models.CharField(max_length=80, blank=True)
    spec_col_6 = models.CharField(max_length=80, blank=True)
    spec_col_7 = models.CharField(max_length=80, blank=True)
    faq_title = models.CharField(max_length=160, blank=True)
    faq_subtitle = models.CharField(max_length=200, blank=True)
    cta_title = models.CharField(max_length=160, blank=True)
    cta_description = models.TextField(blank=True)
    cta_image = models.ImageField(upload_to="electricity/service_pages/cta/", blank=True, null=True)
    cta_primary_label = models.CharField(max_length=80, blank=True)
    cta_primary_url = models.CharField(max_length=240, blank=True)
    cta_secondary_label = models.CharField(max_length=80, blank=True)
    cta_secondary_url = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["parent_category", "menu_group", "order", "name"]

    def __str__(self):
        return self.name


class ServiceDetailSection(models.Model):
    class Kind(models.TextChoices):
        PRODUCTS = "products", "Products"
        FEATURES = "features", "Feature Cards"
        ACCESSORIES = "accessories", "Accessories"

    page = models.ForeignKey(
        ServiceDetailPage,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PRODUCTS)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.name} - {self.title}"


class ServiceDetailContentBlock(models.Model):
    class Layout(models.TextChoices):
        TEXT = "text", "Text only"
        SPLIT_IMAGE_RIGHT = "split_image_right", "Text with image right"
        SPLIT_IMAGE_LEFT = "split_image_left", "Text with image left"
        EMPHASIS = "emphasis", "Emphasis band"
        CHECKLIST = "checklist", "Checklist panel"

    page = models.ForeignKey(
        ServiceDetailPage,
        on_delete=models.CASCADE,
        related_name="content_blocks",
    )
    layout = models.CharField(max_length=24, choices=Layout.choices, default=Layout.TEXT)
    eyebrow = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    secondary_body = models.TextField(blank=True)
    image = models.ImageField(upload_to="electricity/service_pages/blocks/", blank=True, null=True)
    image_alt = models.CharField(max_length=160, blank=True)
    badge = models.CharField(max_length=80, blank=True)
    list_title = models.CharField(max_length=80, blank=True)
    list_lines = models.TextField(blank=True, default="")
    stat_label = models.CharField(max_length=80, blank=True)
    stat_value = models.CharField(max_length=80, blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.name} - {self.title}"


class ServiceDetailItem(models.Model):
    section = models.ForeignKey(
        ServiceDetailSection,
        on_delete=models.CASCADE,
        related_name="items",
    )
    badge = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="electricity/service_pages/items/", blank=True, null=True)
    price_text = models.CharField(max_length=80, blank=True)
    price_note = models.CharField(max_length=80, blank=True)
    meta_lines = models.TextField(blank=True, default="")
    included_title = models.CharField(max_length=80, blank=True)
    included_lines = models.TextField(blank=True, default="")
    excluded_title = models.CharField(max_length=80, blank=True)
    excluded_lines = models.TextField(blank=True, default="")
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=240, blank=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class ServiceDetailSpecRow(models.Model):
    page = models.ForeignKey(
        ServiceDetailPage,
        on_delete=models.CASCADE,
        related_name="spec_rows",
    )
    label = models.CharField(max_length=120)
    value_1 = models.CharField(max_length=160, blank=True)
    value_2 = models.CharField(max_length=160, blank=True)
    value_3 = models.CharField(max_length=160, blank=True)
    value_4 = models.CharField(max_length=160, blank=True)
    value_5 = models.CharField(max_length=160, blank=True)
    value_6 = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.name} - {self.label}"


class ServiceDetailFAQ(models.Model):
    page = models.ForeignKey(
        ServiceDetailPage,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    question = models.CharField(max_length=240)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.question


class ServiceBookingStatusUpdate(models.Model):
    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.CASCADE, related_name="status_updates"
    )
    status = models.CharField(max_length=20, choices=ServiceBooking.Status.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.booking_id} - {self.status}"


class OnCallBooking(models.Model):
    class EntityType(models.TextChoices):
        BUSINESS = "business", "Business / Organization"
        HOUSING = "housing", "Housing Association"

    class ResponseSpeed(models.TextChoices):
        STANDARD = "standard", "Standard response"
        PRIORITY = "priority", "Priority response"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWING = "reviewing", "Reviewing"
        APPROVED = "approved", "Approved"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"

    entity_type = models.CharField(max_length=20, choices=EntityType.choices, blank=True)
    organization_name = models.CharField(max_length=160, blank=True)
    organization_number = models.CharField(max_length=40, blank=True)
    contact_person = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    company_address = models.CharField(max_length=200, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)

    coverage_times = models.JSONField(default=list, blank=True)
    response_speed = models.CharField(max_length=20, choices=ResponseSpeed.choices, blank=True)
    coverage_scope = models.JSONField(default=list, blank=True)

    property_type = models.CharField(max_length=80, blank=True)
    assets_count = models.PositiveIntegerField(default=0)
    primary_region = models.CharField(max_length=120, blank=True)
    shared_critical_systems = models.BooleanField(default=False)

    last_issue_date = models.DateField(null=True, blank=True)
    active_contract = models.BooleanField(default=False)
    recurring_issues = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)

    emergency_hours = models.PositiveIntegerField(default=1)
    hourly_rate_emergency_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    service_plan = models.CharField(max_length=120, default="On-Call Pro (Monthly)")
    site_address = models.CharField(max_length=200, blank=True)

    assigned_provider = models.ForeignKey(
        "ProviderProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_on_call_bookings",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        label = self.organization_name or self.contact_person or "On-Call Booking"
        return f"{label} ({self.get_status_display()})"


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"

    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    request_type = models.CharField(max_length=80, blank=True)
    customer_type = models.CharField(max_length=80, blank=True)
    project_address = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class AcceptedZipCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = re.sub(r"\s+", "", self.code)
        super().save(*args, **kwargs)


class ServiceRequestOutsideArea(models.Model):
    class RequestType(models.TextChoices):
        CONSULTATION = "consultation", "Consultation Booking"
        SERVICE = "service", "Service Booking"
        ON_CALL = "on_call", "On-Call Booking"

    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    zip_code = models.CharField(max_length=10)
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_request_type_display()})"


class ServicePricing(models.Model):
    name = models.CharField(max_length=120, default="Default Pricing")
    labor_rate = models.DecimalField(max_digits=10, decimal_places=2, default=1250)
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=495)
    hourly_rate_electrician = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hourly_rate_emergency = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    consultation_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rot_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    currency = models.CharField(max_length=10, default="SEK")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.currency})"


class ConsultationBooking(models.Model):
    class BookingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ASSIGNED = "assigned", "Assigned"
        ON_THE_WAY = "on_the_way", "On the way"
        STARTED = "started", "Started"
        PAUSED = "paused", "Paused"
        RESUMED = "resumed", "Resumed"
        COMPLETED = "completed", "Completed"
        NOT_AVAILABLE = "not_available", "Arrived but customer not available"
        CANCELED = "canceled", "Canceled"

    class ContactType(models.TextChoices):
        PRIVATE = "private", "Private"
        BUSINESS = "business", "Business"

    class TimeWindow(models.TextChoices):
        MORNING = "morning", "Morning"
        MIDDAY = "midday", "Midday"
        AFTERNOON = "afternoon", "Afternoon"
        EVENING = "evening", "Evening"

    consultation_type = models.CharField(max_length=40, blank=True)
    property_type = models.CharField(max_length=40, blank=True)
    property_type_other = models.CharField(max_length=120, blank=True)
    property_size = models.CharField(max_length=40, blank=True)
    year_built = models.CharField(max_length=10, blank=True)
    services = models.JSONField(default=list, blank=True)
    urgent = models.BooleanField(default=False)
    project_description = models.TextField(blank=True)

    photo = models.ImageField(upload_to="electricity/booking/photos/", blank=True, null=True)
    video = models.FileField(upload_to="electricity/booking/videos/", blank=True, null=True)
    document = models.FileField(upload_to="electricity/booking/docs/", blank=True, null=True)

    contact_type = models.CharField(max_length=20, choices=ContactType.choices, blank=True)
    personal_id = models.CharField(max_length=40, blank=True)
    company_name = models.CharField(max_length=160, blank=True)
    organization_number = models.CharField(max_length=40, blank=True)
    company_address = models.CharField(max_length=220, blank=True)
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    availability_days = models.JSONField(default=list, blank=True)
    time_window = models.CharField(max_length=20, choices=TimeWindow.choices, blank=True)
    preferred_date = models.DateField(blank=True, null=True)
    preferred_time_slot = models.CharField(max_length=60, blank=True)
    assigned_provider = models.ForeignKey(
        "ProviderProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_bookings",
    )
    status = models.CharField(max_length=20, choices=BookingStatus.choices, default=BookingStatus.PENDING)
    status_updated_at = models.DateTimeField(auto_now=True)
    consultation_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_first_free = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.created_at:%Y-%m-%d}"


class ConsultationBookingAttachment(models.Model):
    class AttachmentKind(models.TextChoices):
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"
        DOCUMENT = "document", "Document"

    booking = models.ForeignKey(
        ConsultationBooking,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    kind = models.CharField(max_length=20, choices=AttachmentKind.choices)
    file = models.FileField(upload_to="electricity/booking/attachments/")
    original_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.original_name or self.file.name


class ProviderShift(models.Model):
    provider = models.ForeignKey(
        "ProviderProfile",
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["provider", "weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                check=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="provider_shift_weekday_range",
            ),
        ]

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "Shift end time must be after start time."})


    @property
    def weekday_label(self):
        names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        try:
            return names[self.weekday]
        except Exception:
            return str(self.weekday)

    def __str__(self):
        return f"{self.provider.display_name} - {self.weekday} ({self.start_time}-{self.end_time})"


class ProviderProfile(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="provider_profile")
    display_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.zip_code:
            self.zip_code = re.sub(r"\s+", "", self.zip_code)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name

    @property
    def is_available(self):
        now = timezone.now()
        active_service = self.assigned_service_bookings.exclude(
            status__in=[ServiceBooking.Status.COMPLETED, ServiceBooking.Status.CANCELED]
        ).exclude(start_at__isnull=True).exclude(end_at__isnull=True)
        if active_service.filter(start_at__lte=now, end_at__gt=now).exists():
            return False
        active_consult = self.assigned_bookings.filter(
            status__in=[
                ConsultationBooking.BookingStatus.ASSIGNED,
                ConsultationBooking.BookingStatus.ON_THE_WAY,
                ConsultationBooking.BookingStatus.STARTED,
                ConsultationBooking.BookingStatus.PAUSED,
                ConsultationBooking.BookingStatus.RESUMED,
                ConsultationBooking.BookingStatus.NOT_AVAILABLE,
            ]
        )
        for booking in active_consult:
            if booking.preferred_date != now.date():
                continue
            start_time = None
            for fmt in ("%H:%M", "%I:%M %p"):
                try:
                    start_time = datetime.datetime.strptime(booking.preferred_time_slot, fmt).time()
                    break
                except ValueError:
                    continue
            if not start_time:
                continue
            start_dt = timezone.make_aware(datetime.datetime.combine(booking.preferred_date, start_time))
            end_dt = start_dt + datetime.timedelta(hours=1)
            if start_dt <= now < end_dt:
                return False
        return True

    def next_available_at(self, now=None):
        now = now or timezone.now()
        candidates = []
        active_service = self.assigned_service_bookings.exclude(
            status__in=[ServiceBooking.Status.COMPLETED, ServiceBooking.Status.CANCELED]
        ).exclude(start_at__isnull=True).exclude(end_at__isnull=True)
        active_ranges = active_service.filter(start_at__lte=now, end_at__gt=now).values_list("end_at", flat=True)
        candidates.extend(list(active_ranges))

        active_consult = self.assigned_bookings.filter(
            status__in=[
                ConsultationBooking.BookingStatus.ASSIGNED,
                ConsultationBooking.BookingStatus.ON_THE_WAY,
                ConsultationBooking.BookingStatus.STARTED,
                ConsultationBooking.BookingStatus.PAUSED,
                ConsultationBooking.BookingStatus.RESUMED,
                ConsultationBooking.BookingStatus.NOT_AVAILABLE,
            ]
        )
        for booking in active_consult:
            if booking.preferred_date != now.date():
                continue
            start_time = None
            for fmt in ("%H:%M", "%I:%M %p"):
                try:
                    start_time = datetime.datetime.strptime(booking.preferred_time_slot, fmt).time()
                    break
                except ValueError:
                    continue
            if not start_time:
                continue
            start_dt = timezone.make_aware(datetime.datetime.combine(booking.preferred_date, start_time))
            end_dt = start_dt + datetime.timedelta(hours=1)
            if start_dt <= now < end_dt:
                candidates.append(end_dt)

        if candidates:
            return min(candidates)
        return now

    def available_after_minutes(self, now=None):
        now = now or timezone.now()
        next_time = self.next_available_at(now=now)
        if next_time <= now:
            return 0
        return int((next_time - now).total_seconds() // 60)

    @property
    def availability_status(self):
        minutes = self.available_after_minutes()
        if minutes <= 0:
            return "Available now"
        return f"Available after {minutes} minutes"


class BookingStatusUpdate(models.Model):
    booking = models.ForeignKey(
        ConsultationBooking, on_delete=models.CASCADE, related_name="status_updates"
    )
    status = models.CharField(max_length=20, choices=ConsultationBooking.BookingStatus.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.booking_id} - {self.status}"


class AdminNotification(models.Model):
    booking = models.ForeignKey(
        ConsultationBooking, on_delete=models.CASCADE, related_name="admin_notifications", null=True, blank=True
    )
    consultation_request = models.ForeignKey(
        ConsultationRequest, on_delete=models.CASCADE, related_name="admin_notifications", null=True, blank=True
    )
    service_booking = models.ForeignKey(
        "ServiceBooking", on_delete=models.CASCADE, related_name="admin_notifications", null=True, blank=True
    )
    on_call_booking = models.ForeignKey(
        "OnCallBooking", on_delete=models.CASCADE, related_name="admin_notifications", null=True, blank=True
    )
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message


class CustomerProfile(models.Model):
    class AccountType(models.TextChoices):
        PRIVATE = "private", "Private"
        BUSINESS = "business", "Business"

    user = models.OneToOneField(
        "auth.User", on_delete=models.SET_NULL, related_name="customer_profile", null=True, blank=True
    )
    customer_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    account_type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.PRIVATE)
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    street_address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=60, default="Germany")
    property_type = models.CharField(max_length=40, blank=True)
    property_designation = models.CharField(max_length=120, blank=True)
    interests = models.JSONField(default=list, blank=True)
    personal_id = models.CharField(max_length=40, blank=True)
    company_name = models.CharField(max_length=160, blank=True)
    organization_number = models.CharField(max_length=40, blank=True)
    company_address = models.CharField(max_length=220, blank=True)
    accepted_terms = models.BooleanField(default=False)
    accepted_privacy = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.customer_number:
            last_number = (
                CustomerProfile.objects.exclude(customer_number__isnull=True)
                .order_by("-customer_number")
                .values_list("customer_number", flat=True)
                .first()
            )
            self.customer_number = max(2500, (last_number or 2499) + 1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_number} - {self.full_name}"


class Invoice(models.Model):
    class InvoiceType(models.TextChoices):
        STANDARD = "standard", "Standard invoice"
        ROT = "rot", "ROT invoice"
        MATERIAL = "material", "Material invoice"
        LABOUR = "labour", "Labour invoice"
        PART = "part", "Part invoice"
        CREDIT = "credit", "Credit invoice"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready to send"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"
        CREDITED = "credited", "Credited"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name="invoices")
    recipient_email = models.EmailField(blank=True)
    invoice_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=160, default="Faktura")
    invoice_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    payment_terms_days = models.PositiveSmallIntegerField(default=20)
    invoice_type = models.CharField(max_length=20, choices=InvoiceType.choices, default=InvoiceType.STANDARD)
    part_number = models.PositiveSmallIntegerField(null=True, blank=True)
    part_total = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    reference = models.CharField(max_length=120, blank=True)
    work_address = models.CharField(max_length=240, blank=True)
    currency = models.CharField(max_length=10, default="SEK")
    discount_type = models.CharField(
        max_length=12, choices=(("none", "None"), ("fixed", "Fixed amount"), ("percent", "Percentage")), default="none"
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rot_enabled = models.BooleanField(default=False)
    rot_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    rot_personal_number = models.CharField(max_length=40, blank=True)
    rot_property_designation = models.CharField(max_length=120, blank=True)
    rot_brf_org_number = models.CharField(max_length=40, blank=True)
    rot_apartment_number = models.CharField(max_length=40, blank=True)
    customer_message = models.TextField(blank=True)
    payment_instructions = models.TextField(blank=True, default="Pay to Bankgiro 5192-1302 and state the invoice number.")
    internal_notes = models.TextField(blank=True)
    additional_terms = models.TextField(blank=True)
    rounding = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal_ex_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rot_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_inc_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    consultation_booking = models.OneToOneField(
        "ConsultationBooking", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice"
    )
    service_booking = models.OneToOneField(
        "ServiceBooking", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice"
    )
    electrician_booking = models.OneToOneField(
        "ElectricianBooking", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice"
    )
    on_call_booking = models.OneToOneField(
        "OnCallBooking", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_number"]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last_number = (
                Invoice.objects.exclude(invoice_number__isnull=True)
                .order_by("-invoice_number")
                .values_list("invoice_number", flat=True)
                .first()
            )
            self.invoice_number = max(100, (last_number or 99) + 1)
        if not self.due_date:
            self.due_date = self.invoice_date + datetime.timedelta(days=self.payment_terms_days)
        super().save(*args, **kwargs)

    def recalculate(self, save=True):
        from decimal import Decimal, ROUND_HALF_UP
        rows = list(self.lines.all())
        subtotal = sum((row.total_ex_vat for row in rows), Decimal("0"))
        row_discounts = sum((row.discount_amount for row in rows), Decimal("0"))
        invoice_discount = Decimal("0")
        base_after_rows = subtotal - row_discounts
        if self.discount_type == "fixed":
            invoice_discount = min(self.discount_value, base_after_rows)
        elif self.discount_type == "percent":
            invoice_discount = base_after_rows * self.discount_value / Decimal("100")
        ratio = (base_after_rows - invoice_discount) / base_after_rows if base_after_rows else Decimal("1")
        vat = sum(((row.total_ex_vat - row.discount_amount) * ratio * row.vat_percent / Decimal("100") for row in rows), Decimal("0"))
        total_inc = base_after_rows - invoice_discount + vat
        rot_eligible_inc = sum(
            ((row.total_ex_vat - row.discount_amount) * ratio * (Decimal("1") + row.vat_percent / Decimal("100"))
             for row in rows if row.category == InvoiceLine.Category.LABOUR and row.rot_eligible),
            Decimal("0"),
        )
        rot = rot_eligible_inc * self.rot_percent / Decimal("100") if self.rot_enabled else Decimal("0")
        q = Decimal("0.01")
        self.subtotal_ex_vat = subtotal.quantize(q, ROUND_HALF_UP)
        self.discount_total = (row_discounts + invoice_discount).quantize(q, ROUND_HALF_UP)
        self.vat_total = vat.quantize(q, ROUND_HALF_UP)
        self.total_inc_vat = total_inc.quantize(q, ROUND_HALF_UP)
        self.rot_total = rot.quantize(q, ROUND_HALF_UP)
        self.amount_due = (total_inc - rot + self.rounding - self.amount_paid).quantize(q, ROUND_HALF_UP)
        if save:
            super().save(update_fields=[
                "subtotal_ex_vat", "discount_total", "vat_total", "total_inc_vat",
                "rot_total", "amount_due", "updated_at"
            ])

    def __str__(self):
        return f"{self.title} {self.invoice_number}"


class InvoiceLine(models.Model):
    class Category(models.TextChoices):
        LABOUR = "labour", "Labour"
        MATERIAL = "material", "Material"
        TRANSPORT = "transport", "Transport"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.LABOUR)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=30, default="fixed price")
    unit_price_ex_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(
        max_length=12, choices=(("none", "None"), ("fixed", "Fixed amount"), ("percent", "Percentage")), default="none"
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    rot_eligible = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    @property
    def total_ex_vat(self):
        return self.quantity * self.unit_price_ex_vat

    @property
    def discount_amount(self):
        if self.discount_type == "fixed":
            return min(self.discount_value, self.total_ex_vat)
        if self.discount_type == "percent":
            return self.total_ex_vat * self.discount_value / Decimal("100")
        return Decimal("0")

    @property
    def total_inc_vat(self):
        net = self.total_ex_vat - self.discount_amount
        return net * (Decimal("1") + self.vat_percent / Decimal("100"))

    def clean(self):
        if self.rot_eligible and self.category != self.Category.LABOUR:
            raise ValidationError({"rot_eligible": "Only labour rows can be ROT eligible."})


class CustomerFeedback(models.Model):
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    message = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(rating__gte=1) & Q(rating__lte=5),
                name="customer_feedback_rating_range",
            ),
        ]

    def __str__(self):
        state = "approved" if self.is_approved else "pending"
        return f"{self.full_name} ({state})"
