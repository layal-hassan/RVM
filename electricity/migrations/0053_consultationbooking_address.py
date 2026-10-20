from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0052_align_electrician_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="consultationbooking",
            name="street_address",
            field=models.CharField(blank=True, max_length=220),
        ),
        migrations.AddField(
            model_name="consultationbooking",
            name="postal_code",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="consultationbooking",
            name="city",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
