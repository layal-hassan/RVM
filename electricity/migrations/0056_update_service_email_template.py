from django.db import migrations


def update_service_template(apps, schema_editor):
    Template = apps.get_model("electricity", "AutomatedEmailTemplate")
    Template.objects.filter(workflow="service").update(
        customer_body=(
            "Hello {name},\n\nWe received your service booking successfully.\n\n"
            "Reference: {reference}\nRequested date: {preferred_date}\nRequested time: {preferred_time}\n\n"
            "Summary:\n{details}\n\nOur team will contact you with the next steps.\n\nKind regards,\nRWM EL"
        )
    )


class Migration(migrations.Migration):
    dependencies = [("electricity", "0055_expand_automated_email_workflows")]
    operations = [migrations.RunPython(update_service_template, migrations.RunPython.noop)]
