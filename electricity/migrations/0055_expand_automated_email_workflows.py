from django.db import migrations, models


WORKFLOWS = {
    "consultation": {
        "label": "Consultation Booking",
        "company_subject": "New consultation booking {reference} - {name}",
        "company_body": "Reference: {reference}\nCustomer: {name}\nEmail: {email}\nPhone: {phone}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\nDetails:\n{details}",
        "customer_subject": "Consultation booking received - {reference}",
        "customer_body": "Hello {name},\n\nWe received your consultation booking.\n\nReference: {reference}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\nOur team will contact you to confirm the details.\n\nKind regards,\nRWM EL",
    },
    "electrician": {
        "label": "Electrician Booking",
        "company_subject": "New electrician booking {reference} - {name}",
        "company_body": "Reference: {reference}\nCustomer: {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\nDetails:\n{details}",
        "customer_subject": "Electrician booking received - {reference}",
        "customer_body": "Hello {name},\n\nWe received your electrician booking successfully.\n\nReference: {reference}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\nOur team will review your request and contact you if anything needs to be confirmed.\n\nKind regards,\nRWM EL",
    },
    "service": {
        "label": "Service Booking",
        "company_subject": "New service booking {reference} - {name}",
        "company_body": "Reference: {reference}\nCustomer: {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\nDetails:\n{details}",
        "customer_subject": "Service booking received - {reference}",
        "customer_body": "Hello {name},\n\nWe received your service booking successfully.\n\nReference: {reference}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\nOur team will contact you with the next steps.\n\nKind regards,\nRWM EL",
    },
    "on_call": {
        "label": "On-Call Booking",
        "company_subject": "New on-call application {reference} - {name}",
        "company_body": "Reference: {reference}\nOrganization: {name}\nEmail: {email}\nPhone: {phone}\nAddress: {address}\n\nDetails:\n{details}",
        "customer_subject": "On-call application received - {reference}",
        "customer_body": "Hello {name},\n\nWe received your on-call service application.\n\nReference: {reference}\n\nOur team will review the information and contact you with the next steps.\n\nKind regards,\nRWM EL",
    },
}


def create_booking_templates(apps, schema_editor):
    Template = apps.get_model("electricity", "AutomatedEmailTemplate")
    for workflow, values in WORKFLOWS.items():
        Template.objects.get_or_create(
            workflow=workflow,
            defaults={
                "company_enabled": True,
                "company_subject": values["company_subject"],
                "company_body": values["company_body"],
                "customer_enabled": True,
                "customer_subject": values["customer_subject"],
                "customer_body": values["customer_body"],
            },
        )


class Migration(migrations.Migration):
    dependencies = [("electricity", "0055_align_customer_facing_pricing")]

    operations = [
        migrations.AlterField(
            model_name="automatedemailtemplate",
            name="workflow",
            field=models.CharField(
                choices=[
                    ("contact", "Contact Us"),
                    ("feedback", "Submit Feedback"),
                    ("quote", "Request a Quote / Send Request"),
                    ("consultation", "Consultation Booking"),
                    ("electrician", "Electrician Booking"),
                    ("service", "Service Booking"),
                    ("on_call", "On-Call Booking"),
                ],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.RunPython(create_booking_templates, migrations.RunPython.noop),
    ]
