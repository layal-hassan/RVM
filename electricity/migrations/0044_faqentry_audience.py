from django.db import migrations, models


BRF_FAQS = (
    (
        "Do you work with service agreements for BRFs?",
        "Yes. We offer flexible service agreements tailored to your property, maintenance needs and preferred response times.",
    ),
    (
        "What types of electrical work do you handle?",
        "We handle maintenance, fault finding, lighting, EV charging, electrical upgrades and other installations for shared properties.",
    ),
    (
        "How quickly can you respond to urgent issues?",
        "Response time depends on availability and the nature of the issue. Contact us directly and we will prioritise urgent safety concerns.",
    ),
    (
        "Do you provide quotations before starting work?",
        "Yes. You receive a clear quotation and recommendations before any planned work begins.",
    ),
)


def create_brf_faqs(apps, schema_editor):
    FAQEntry = apps.get_model("electricity", "FAQEntry")
    for order, (question, answer) in enumerate(BRF_FAQS, start=1):
        FAQEntry.objects.get_or_create(
            audience="brf",
            question_en=question,
            defaults={
                "question": question,
                "answer": answer,
                "answer_en": answer,
                "is_active": True,
                "order": order,
            },
        )


def remove_brf_faqs(apps, schema_editor):
    FAQEntry = apps.get_model("electricity", "FAQEntry")
    FAQEntry.objects.filter(
        audience="brf",
        question_en__in=[question for question, _answer in BRF_FAQS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("electricity", "0043_homeheropricing")]

    operations = [
        migrations.AddField(
            model_name="faqentry",
            name="audience",
            field=models.CharField(
                choices=[("general", "General FAQ page"), ("brf", "For BRF page")],
                default="general",
                max_length=20,
            ),
        ),
        migrations.RunPython(create_brf_faqs, remove_brf_faqs),
    ]
