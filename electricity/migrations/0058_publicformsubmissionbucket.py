from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("electricity", "0057_update_service_email_next_steps")]

    operations = [
        migrations.CreateModel(
            name="PublicFormSubmissionBucket",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("count", models.PositiveIntegerField(default=0)),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
        ),
    ]
