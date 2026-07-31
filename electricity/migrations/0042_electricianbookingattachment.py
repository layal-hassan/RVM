from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("electricity", "0041_invoice_recipient_email")]

    operations = [
        migrations.CreateModel(
            name="ElectricianBookingAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="electricity/electrician_booking/attachments/")),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="electricity.electricianbooking")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
