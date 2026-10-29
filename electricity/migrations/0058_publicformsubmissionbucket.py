from django.db import migrations, models


class Migration(migrations.Migration):
    # This independent table must not force pending template/data updates.
    dependencies = [("electricity", "0054_automatedemailtemplate")]

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
