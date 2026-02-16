from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0012_adminnotification_extensions"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=160)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("request_type", models.CharField(blank=True, max_length=80)),
                ("customer_type", models.CharField(blank=True, max_length=80)),
                ("project_address", models.CharField(blank=True, max_length=200)),
                ("message", models.TextField()),
                ("status", models.CharField(choices=[("new", "New"), ("in_progress", "In Progress"), ("resolved", "Resolved")], default="new", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]

