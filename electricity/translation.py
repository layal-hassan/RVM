from modeltranslation.translator import TranslationOptions, register

from .models import AdminNotification, ElectricalService, FAQEntry, ServicePricing


@register(ElectricalService)
class ElectricalServiceTranslationOptions(TranslationOptions):
    fields = ("title", "short_description", "bullet_points")


@register(FAQEntry)
class FAQEntryTranslationOptions(TranslationOptions):
    fields = ("question", "answer")


@register(ServicePricing)
class ServicePricingTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(AdminNotification)
class AdminNotificationTranslationOptions(TranslationOptions):
    fields = ("message",)
