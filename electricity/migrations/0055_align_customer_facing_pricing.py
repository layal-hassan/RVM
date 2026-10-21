from decimal import Decimal

from django.db import migrations, models


def align_customer_facing_pricing(apps, schema_editor):
    ServicePricing = apps.get_model("electricity", "ServicePricing")
    ServicePricing.objects.filter(is_active=True).update(
        labor_rate=Decimal("688.00"),
        hourly_rate_electrician=Decimal("688.00"),
        transport_fee=Decimal("500.00"),
        rot_percent=Decimal("30.00"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0054_automatedemailtemplate"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicepricing",
            name="labor_rate",
            field=models.DecimalField(decimal_places=2, default=688, max_digits=10),
        ),
        migrations.AlterField(
            model_name="servicepricing",
            name="hourly_rate_electrician",
            field=models.DecimalField(decimal_places=2, default=Decimal("688.00"), max_digits=10),
        ),
        migrations.AlterField(
            model_name="servicepricing",
            name="transport_fee",
            field=models.DecimalField(decimal_places=2, default=500, max_digits=10),
        ),
        migrations.RunPython(align_customer_facing_pricing, migrations.RunPython.noop),
    ]
