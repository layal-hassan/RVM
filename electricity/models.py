import datetime
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone


class ElectricalService(models.Model):
    title = models.CharField(max_length=120)
    short_description = models.TextField()
    bullet_points = models.TextField(blank=True, default="")
    icon = models.ImageField(upload_to='electricity/services/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_minutes = models.PositiveIntegerField(default=0)
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

    def clean(self):
        errors = {}
        if self.price is None or self.price <= 0:
            errors["price"] = "Price must be greater than 0."
        if not self.duration_minutes or self.duration_minutes <= 0:
            errors["duration_minutes"] = "Duration must be greater than 0."
        if errors:
            raise ValidationError(errors)

    @property
    def is_bookable(self):
        return self.is_active and self.price > 0 and self.duration_minutes > 0

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
        self.code = self.code.replace(" ", "")
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

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="customer_profile")
    account_type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.PRIVATE)
    full_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    street_address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=60, default="Germany")
    property_type = models.CharField(max_length=40, blank=True)
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

    def __str__(self):
        return f"{self.full_name} ({self.account_type})"
