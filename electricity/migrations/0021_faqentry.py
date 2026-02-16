from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0020_electricianbooking_assigned_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="FAQEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.CharField(max_length=240)),
                ("answer", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["order", "-created_at"],
            },
        ),
    ]
