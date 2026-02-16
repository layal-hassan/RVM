from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0019_electricianbooking"),
    ]

    operations = [
        migrations.AddField(
            model_name="electricianbooking",
            name="assigned_provider",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_electrician_bookings",
                to="electricity.providerprofile",
            ),
        ),
    ]
