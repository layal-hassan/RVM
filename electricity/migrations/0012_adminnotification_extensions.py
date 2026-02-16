from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0011_oncallbooking"),
    ]

    operations = [
        migrations.AlterField(
            model_name="adminnotification",
            name="booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="admin_notifications",
                to="electricity.consultationbooking",
            ),
        ),
        migrations.AddField(
            model_name="adminnotification",
            name="consultation_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="admin_notifications",
                to="electricity.consultationrequest",
            ),
        ),
        migrations.AddField(
            model_name="adminnotification",
            name="service_booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="admin_notifications",
                to="electricity.servicebooking",
            ),
        ),
        migrations.AddField(
            model_name="adminnotification",
            name="on_call_booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="admin_notifications",
                to="electricity.oncallbooking",
            ),
        ),
    ]

