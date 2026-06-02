from modeltranslation.translator import TranslationOptions, register

from .models import (
    AdminNotification,
    ElectricalService,
    FAQEntry,
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
)


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


@register(ServiceCategoryPage)
class ServiceCategoryPageTranslationOptions(TranslationOptions):
    fields = (
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
        "faq_title",
        "faq_subtitle",
        "cta_title",
        "cta_description",
        "cta_primary_label",
        "cta_secondary_label",
    )


@register(ServiceCategorySection)
class ServiceCategorySectionTranslationOptions(TranslationOptions):
    fields = ("title", "subtitle", "description")


@register(ServiceCategoryContentBlock)
class ServiceCategoryContentBlockTranslationOptions(TranslationOptions):
    fields = (
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
    )


@register(ServiceCategoryItem)
class ServiceCategoryItemTranslationOptions(TranslationOptions):
    fields = (
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
    )


@register(ServiceCategorySpecRow)
class ServiceCategorySpecRowTranslationOptions(TranslationOptions):
    fields = ("label", "value_1", "value_2", "value_3", "value_4")


@register(ServiceCategoryFAQ)
class ServiceCategoryFAQTranslationOptions(TranslationOptions):
    fields = ("question", "answer")


@register(ServiceDetailPage)
class ServiceDetailPageTranslationOptions(TranslationOptions):
    fields = (
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
        "faq_title",
        "faq_subtitle",
        "cta_title",
        "cta_description",
        "cta_primary_label",
        "cta_secondary_label",
    )


@register(ServiceDetailSection)
class ServiceDetailSectionTranslationOptions(TranslationOptions):
    fields = ("title", "subtitle", "description")


@register(ServiceDetailContentBlock)
class ServiceDetailContentBlockTranslationOptions(TranslationOptions):
    fields = (
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
    )


@register(ServiceDetailItem)
class ServiceDetailItemTranslationOptions(TranslationOptions):
    fields = (
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
    )


@register(ServiceDetailSpecRow)
class ServiceDetailSpecRowTranslationOptions(TranslationOptions):
    fields = ("label", "value_1", "value_2", "value_3", "value_4")


@register(ServiceDetailFAQ)
class ServiceDetailFAQTranslationOptions(TranslationOptions):
    fields = ("question", "answer")
