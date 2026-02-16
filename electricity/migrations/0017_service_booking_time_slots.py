from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0016_acceptedzipcode_servicerequestoutsidearea"),
    ]

    operations = [
        migrations.AddField(
            model_name="electricalservice",
            name="price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="electricalservice",
            name="duration_minutes",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="zip_code",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="duration_minutes",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="start_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicebooking",
            name="end_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="providerprofile",
            name="zip_code",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.CreateModel(
            name="ProviderShift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("weekday", models.PositiveSmallIntegerField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shifts",
                        to="electricity.providerprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["provider", "weekday", "start_time"],
            },
        ),
        migrations.AddConstraint(
            model_name="providershift",
            constraint=models.CheckConstraint(
                check=models.Q(("weekday__gte", 0), ("weekday__lte", 6)),
                name="provider_shift_weekday_range",
            ),
        ),
    ]
