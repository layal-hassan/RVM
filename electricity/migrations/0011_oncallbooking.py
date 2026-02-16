from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0010_service_pricing_fields_on_services"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnCallBooking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entity_type", models.CharField(blank=True, choices=[("business", "Business / Organization"), ("housing", "Housing Association")], max_length=20)),
                ("organization_name", models.CharField(blank=True, max_length=160)),
                ("organization_number", models.CharField(blank=True, max_length=40)),
                ("contact_person", models.CharField(blank=True, max_length=160)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("company_address", models.CharField(blank=True, max_length=200)),
                ("zip_code", models.CharField(blank=True, max_length=20)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("coverage_times", models.JSONField(blank=True, default=list)),
                ("response_speed", models.CharField(blank=True, choices=[("standard", "Standard response"), ("priority", "Priority response")], max_length=20)),
                ("coverage_scope", models.JSONField(blank=True, default=list)),
                ("property_type", models.CharField(blank=True, max_length=80)),
                ("assets_count", models.PositiveIntegerField(default=0)),
                ("primary_region", models.CharField(blank=True, max_length=120)),
                ("shared_critical_systems", models.BooleanField(default=False)),
                ("last_issue_date", models.DateField(blank=True, null=True)),
                ("active_contract", models.BooleanField(default=False)),
                ("recurring_issues", models.TextField(blank=True)),
                ("additional_notes", models.TextField(blank=True)),
                ("service_plan", models.CharField(default="On-Call Pro (Monthly)", max_length=120)),
                ("site_address", models.CharField(blank=True, max_length=200)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("reviewing", "Reviewing"), ("approved", "Approved"), ("active", "Active"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]

