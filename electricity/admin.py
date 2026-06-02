from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from .admin_site import electricity_admin_site
from .models import (
    AcceptedZipCode,
    ConsultationBooking,
    ConsultationRequest,
    CustomerFeedback,
    ElectricalService,
    OnCallBooking,
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


class CustomerFeedbackAdmin(admin.ModelAdmin):
    list_display = ("full_name", "location", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("full_name", "email", "location", "message")
    ordering = ("-created_at",)


class ServiceCategoryItemInline(admin.StackedInline):
    model = ServiceCategoryItem
    extra = 0


class ServiceCategorySectionInline(admin.StackedInline):
    model = ServiceCategorySection
    extra = 0


class ServiceCategoryContentBlockInline(admin.StackedInline):
    model = ServiceCategoryContentBlock
    extra = 0


class ServiceCategorySpecRowInline(admin.TabularInline):
    model = ServiceCategorySpecRow
    extra = 0


class ServiceCategoryFAQInline(admin.StackedInline):
    model = ServiceCategoryFAQ
    extra = 0


class ServiceCategorySectionAdmin(TranslationAdmin):
    list_display = ("title", "page", "kind", "order")
    list_filter = ("kind", "page")
    inlines = [ServiceCategoryItemInline]


class ServiceCategoryContentBlockAdmin(TranslationAdmin):
    list_display = ("title", "page", "target_service_page", "layout", "is_active", "order")
    list_filter = ("layout", "page", "target_service_page", "is_active")
    search_fields = ("title", "eyebrow", "badge")


class ServiceCategoryPageAdmin(TranslationAdmin):
    list_display = ("name", "theme", "slug", "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("theme", "is_active")
    search_fields = ("name", "slug", "nav_label")
    inlines = [ServiceCategoryContentBlockInline, ServiceCategorySectionInline, ServiceCategorySpecRowInline, ServiceCategoryFAQInline]


class ServiceDetailItemInline(admin.StackedInline):
    model = ServiceDetailItem
    extra = 0


class ServiceDetailSectionInline(admin.StackedInline):
    model = ServiceDetailSection
    extra = 0


class ServiceDetailContentBlockInline(admin.StackedInline):
    model = ServiceDetailContentBlock
    extra = 0


class ServiceDetailSpecRowInline(admin.TabularInline):
    model = ServiceDetailSpecRow
    extra = 0


class ServiceDetailFAQInline(admin.StackedInline):
    model = ServiceDetailFAQ
    extra = 0


class ServiceDetailSectionAdmin(TranslationAdmin):
    list_display = ("title", "page", "kind", "order")
    list_filter = ("kind", "page")
    inlines = [ServiceDetailItemInline]


class ServiceDetailContentBlockAdmin(TranslationAdmin):
    list_display = ("title", "page", "layout", "is_active", "order")
    list_filter = ("layout", "page", "is_active")
    search_fields = ("title", "eyebrow", "badge")


class ServiceDetailPageAdmin(TranslationAdmin):
    list_display = ("name", "parent_category", "menu_group", "slug", "is_active", "order")
    list_filter = ("parent_category", "menu_group", "is_active")
    search_fields = ("name", "slug", "menu_group")
    inlines = [ServiceDetailContentBlockInline, ServiceDetailSectionInline, ServiceDetailSpecRowInline, ServiceDetailFAQInline]


admin.site.register(ElectricalService, ElectricalServiceAdmin)
admin.site.register(ConsultationRequest, ConsultationRequestAdmin)
admin.site.register(ConsultationBooking, ConsultationBookingAdmin)
admin.site.register(ServiceBooking, ServiceBookingAdmin)
admin.site.register(OnCallBooking, OnCallBookingAdmin)
admin.site.register(ServiceCategoryPage, ServiceCategoryPageAdmin)
admin.site.register(ServiceCategoryContentBlock, ServiceCategoryContentBlockAdmin)
admin.site.register(ServiceCategorySection, ServiceCategorySectionAdmin)
admin.site.register(ServiceDetailPage, ServiceDetailPageAdmin)
admin.site.register(ServiceDetailContentBlock, ServiceDetailContentBlockAdmin)
admin.site.register(ServiceDetailSection, ServiceDetailSectionAdmin)
admin.site.register(ServicePricing, ServicePricingAdmin)
admin.site.register(SupportTicket, SupportTicketAdmin)
admin.site.register(CustomerFeedback, CustomerFeedbackAdmin)
admin.site.register(AcceptedZipCode, AcceptedZipCodeAdmin)
admin.site.register(ServiceRequestOutsideArea, ServiceRequestOutsideAreaAdmin)
admin.site.register(ProviderShift, ProviderShiftAdmin)

electricity_admin_site.register(ElectricalService, ElectricalServiceAdmin)
electricity_admin_site.register(ConsultationRequest, ConsultationRequestAdmin)
electricity_admin_site.register(ConsultationBooking, ConsultationBookingAdmin)
electricity_admin_site.register(ServiceBooking, ServiceBookingAdmin)
electricity_admin_site.register(OnCallBooking, OnCallBookingAdmin)
electricity_admin_site.register(ServiceCategoryPage, ServiceCategoryPageAdmin)
electricity_admin_site.register(ServiceCategoryContentBlock, ServiceCategoryContentBlockAdmin)
electricity_admin_site.register(ServiceCategorySection, ServiceCategorySectionAdmin)
electricity_admin_site.register(ServiceDetailPage, ServiceDetailPageAdmin)
electricity_admin_site.register(ServiceDetailContentBlock, ServiceDetailContentBlockAdmin)
electricity_admin_site.register(ServiceDetailSection, ServiceDetailSectionAdmin)
electricity_admin_site.register(ServicePricing, ServicePricingAdmin)
electricity_admin_site.register(SupportTicket, SupportTicketAdmin)
electricity_admin_site.register(CustomerFeedback, CustomerFeedbackAdmin)
electricity_admin_site.register(AcceptedZipCode, AcceptedZipCodeAdmin)
electricity_admin_site.register(ServiceRequestOutsideArea, ServiceRequestOutsideAreaAdmin)
electricity_admin_site.register(ProviderShift, ProviderShiftAdmin)
