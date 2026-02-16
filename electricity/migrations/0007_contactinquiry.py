from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0006_consultationbooking_status_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactInquiry",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=160)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("address", models.CharField(blank=True, max_length=200)),
                ("request_type", models.CharField(blank=True, max_length=80)),
                (
                    "inquiry_type",
                    models.CharField(
                        choices=[
                            ("new_booking", "New service bookings"),
                            ("consultation", "Professional consultations"),
                            ("tech_support", "Technical questions & support"),
                        ],
                        max_length=40,
                    ),
                ),
                ("message", models.TextField()),
                ("consent", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
