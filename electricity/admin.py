from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from .admin_site import electricity_admin_site
from .models import (
    AcceptedZipCode,
    ConsultationBooking,
    ConsultationRequest,
    ElectricalService,
    OnCallBooking,
    ServicePricing,
    ServiceBooking,
    ProviderShift,
    ServiceRequestOutsideArea,
    SupportTicket,
)


class ElectricalServiceAdmin(TranslationAdmin):
    list_display = ("title", "price", "duration_minutes", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("title",)
    ordering = ("order", "title")


class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "service", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "phone", "email")
    ordering = ("-created_at",)


class ConsultationBookingAdmin(admin.ModelAdmin):
    list_display = ("full_name", "consultation_type", "property_type", "urgent", "consultation_price", "is_first_free", "created_at")
    list_filter = ("consultation_type", "property_type", "urgent", "created_at")
    search_fields = ("full_name", "email", "phone")
    ordering = ("-created_at",)


class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ("full_name", "account_type", "pricing_type", "preferred_date", "preferred_time_slot", "status", "created_at")
    list_filter = ("account_type", "status", "created_at")
    search_fields = ("full_name", "email", "phone")
    ordering = ("-created_at",)


class OnCallBookingAdmin(admin.ModelAdmin):
    list_display = (
        "organization_name",
        "contact_person",
        "phone",
        "email",
        "city",
        "response_speed",
        "emergency_hours",
        "estimated_total",
        "status",
        "created_at",
    )
    list_filter = ("entity_type", "response_speed", "status", "created_at")
    ordering = ("-created_at",)


class ServicePricingAdmin(TranslationAdmin):
    list_display = (
        "name",
        "labor_rate",
        "transport_fee",
        "hourly_rate_electrician",
        "hourly_rate_emergency",
        "consultation_price",
        "rot_percent",
        "currency",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "currency", "created_at")


class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "email", "phone")
    ordering = ("-created_at",)


class AcceptedZipCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "is_active", "note", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("code", "note")
    ordering = ("code",)


class ServiceRequestOutsideAreaAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "zip_code", "request_type", "created_at")
    list_filter = ("request_type", "created_at")
    search_fields = ("full_name", "email", "phone", "zip_code")
    ordering = ("-created_at",)


class ProviderShiftAdmin(admin.ModelAdmin):
    list_display = ("provider", "weekday", "start_time", "end_time")
    list_filter = ("weekday",)
    ordering = ("provider", "weekday", "start_time")


admin.site.register(ElectricalService, ElectricalServiceAdmin)
admin.site.register(ConsultationRequest, ConsultationRequestAdmin)
admin.site.register(ConsultationBooking, ConsultationBookingAdmin)
admin.site.register(ServiceBooking, ServiceBookingAdmin)
admin.site.register(OnCallBooking, OnCallBookingAdmin)
admin.site.register(ServicePricing, ServicePricingAdmin)
admin.site.register(SupportTicket, SupportTicketAdmin)
admin.site.register(AcceptedZipCode, AcceptedZipCodeAdmin)
admin.site.register(ServiceRequestOutsideArea, ServiceRequestOutsideAreaAdmin)
admin.site.register(ProviderShift, ProviderShiftAdmin)

electricity_admin_site.register(ElectricalService, ElectricalServiceAdmin)
electricity_admin_site.register(ConsultationRequest, ConsultationRequestAdmin)
electricity_admin_site.register(ConsultationBooking, ConsultationBookingAdmin)
electricity_admin_site.register(ServiceBooking, ServiceBookingAdmin)
electricity_admin_site.register(OnCallBooking, OnCallBookingAdmin)
electricity_admin_site.register(ServicePricing, ServicePricingAdmin)
electricity_admin_site.register(SupportTicket, SupportTicketAdmin)
electricity_admin_site.register(AcceptedZipCode, AcceptedZipCodeAdmin)
electricity_admin_site.register(ServiceRequestOutsideArea, ServiceRequestOutsideAreaAdmin)
electricity_admin_site.register(ProviderShift, ProviderShiftAdmin)
