from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0009_servicepricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="electricalservice",
            name="service_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="base_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="hourly_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="night_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="transport_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="rot_percent",
            field=models.DecimalField(decimal_places=2, default=30, max_digits=5),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="currency",
            field=models.CharField(default="SEK", max_length=10),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="base_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="service_fee_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="night_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="currency",
            field=models.CharField(default="SEK", max_length=10),
        ),
    ]

