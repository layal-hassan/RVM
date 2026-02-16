from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0008_servicebooking"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServicePricing",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Default Pricing", max_length=120)),
                ("labor_rate", models.DecimalField(decimal_places=2, default=1250, max_digits=10)),
                ("transport_fee", models.DecimalField(decimal_places=2, default=495, max_digits=10)),
                ("rot_percent", models.DecimalField(decimal_places=2, default=30, max_digits=5)),
                ("currency", models.CharField(default="SEK", max_length=10)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
