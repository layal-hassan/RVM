from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0024_consultationbookingattachment"),
    ]

    operations = [
        migrations.AddField(
            model_name="electricianbooking",
            name="transport_fee_snapshot",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
