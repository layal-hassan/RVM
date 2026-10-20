from django.db import migrations, models


DEFAULTS = {
    "contact": {
        "company_subject": "New contact request from {name}",
        "company_body": "Name: {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\nService: {service}\n\nMessage:\n{message}",
        "customer_subject": "RWM EL - We received your enquiry",
        "customer_body": "Hello {name},\n\nThank you for contacting RWM EL. We received your enquiry and will get back to you as soon as possible.\n\nService: {service}\nYour message:\n{message}\n\nKind regards,\nRWM EL",
    },
    "feedback": {
        "company_subject": "New customer feedback from {name}",
        "company_body": "Name: {name}\nEmail: {email}\nLocation: {location}\nRating: {rating}/5\n\nFeedback:\n{message}\n\nThis feedback is pending review in the dashboard.",
        "customer_subject": "RWM EL - Feedback received",
        "customer_body": "Hello {name},\n\nThank you for sharing your feedback with RWM EL. We received it successfully and our team will review it.\n\nRating: {rating}/5\nYour message: {message}\n\nKind regards,\nRWM EL",
    },
    "quote": {
        "company_subject": "New quote request {reference} - {name}",
        "company_body": "Reference: {reference}\nCustomer: {name}\nType: {customer_type}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\nService: {service}\n\nRequest details:\n{details}",
        "customer_subject": "Your quote request {reference} has been received",
        "customer_body": "Hello {name},\n\nThank you! We received your request. Our team will review it and get back to you with a tailored quotation.\n\nService: {service}\nReference: {reference}\n\nKind regards,\nRWM EL",
    },
}


def create_default_templates(apps, schema_editor):
    AutomatedEmailTemplate = apps.get_model("electricity", "AutomatedEmailTemplate")
    for workflow, values in DEFAULTS.items():
        AutomatedEmailTemplate.objects.get_or_create(workflow=workflow, defaults=values)


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0053_consultationbooking_address"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomatedEmailTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("workflow", models.CharField(choices=[("contact", "Contact Us"), ("feedback", "Submit Feedback"), ("quote", "Request a Quote / Send Request")], max_length=20, unique=True)),
                ("company_enabled", models.BooleanField(default=True)),
                ("company_recipient", models.EmailField(blank=True, help_text="Leave blank to use CONTACT_TO_EMAIL from the server settings.", max_length=254)),
                ("company_subject", models.CharField(max_length=240)),
                ("company_body", models.TextField()),
                ("customer_enabled", models.BooleanField(default=True)),
                ("customer_subject", models.CharField(max_length=240)),
                ("customer_body", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["workflow"]},
        ),
        migrations.RunPython(create_default_templates, migrations.RunPython.noop),
    ]
