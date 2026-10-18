from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0049_servicecategoryitem_pricing_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicedetailitem",
            name="pricing_mode",
            field=models.CharField(
                choices=[("fixed", "Fixed price"), ("quote", "Request a quote")],
                default="fixed",
                help_text="Choose whether this card shows a price or asks the customer to request a quote.",
                max_length=12,
            ),
        ),
    ]
