from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("electricity", "0026_electricianbooking_rot_percent_snapshot_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="electricalservice",
            name="short_description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
