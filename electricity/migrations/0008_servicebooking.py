from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0007_contactinquiry"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceBooking",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "account_type",
                    models.CharField(
                        choices=[("private", "Private Customer"), ("business", "Business / BRF")],
                        max_length=20,
                    ),
                ),
                ("full_name", models.CharField(max_length=160)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("street_address", models.CharField(blank=True, max_length=200)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("region", models.CharField(blank=True, max_length=80)),
                ("country", models.CharField(default="Sweden", max_length=60)),
                ("property_type", models.CharField(blank=True, max_length=60)),
                ("year_built", models.CharField(blank=True, max_length=20)),
                ("property_size", models.CharField(blank=True, max_length=40)),
                ("system_upgraded", models.BooleanField(default=False)),
                ("services", models.JSONField(blank=True, default=list)),
                ("work_description", models.TextField(blank=True)),
                ("urgent", models.BooleanField(default=False)),
                ("preferred_date", models.DateField(blank=True, null=True)),
                ("preferred_time_slot", models.CharField(blank=True, max_length=60)),
                ("alt_date", models.DateField(blank=True, null=True)),
                ("alt_time_slot", models.CharField(blank=True, max_length=60)),
                ("labor_rate", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("transport_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("promo_code", models.CharField(blank=True, max_length=40)),
                ("rot_deduction", models.BooleanField(default=False)),
                ("estimated_total", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                (
                    "billing_type",
                    models.CharField(
                        blank=True,
                        choices=[("private", "Private (Personal ID)"), ("business", "Business (Org Number)")],
                        max_length=20,
                    ),
                ),
                ("personal_id", models.CharField(blank=True, max_length=40)),
                ("organization_number", models.CharField(blank=True, max_length=40)),
                ("company_name", models.CharField(blank=True, max_length=160)),
                ("brf_property", models.BooleanField(default=False)),
                ("brf_name", models.CharField(blank=True, max_length=120)),
                ("apartment_number", models.CharField(blank=True, max_length=20)),
                ("uploads", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("scheduled", "Scheduled"),
                            ("completed", "Completed"),
                            ("canceled", "Canceled"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
