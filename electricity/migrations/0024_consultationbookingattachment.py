from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0023_alter_electricalservice_duration_minutes_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsultationBookingAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[("photo", "Photo"), ("video", "Video"), ("document", "Document")],
                        max_length=20,
                    ),
                ),
                ("file", models.FileField(upload_to="electricity/booking/attachments/")),
                ("original_name", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="electricity.consultationbooking",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
