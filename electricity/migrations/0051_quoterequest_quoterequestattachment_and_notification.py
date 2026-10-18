from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("electricity", "0050_servicedetailitem_pricing_mode")]
    operations = [
        migrations.CreateModel(
            name="QuoteRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("service_title", models.CharField(max_length=160)),
                ("service_description", models.TextField(blank=True)),
                ("service_image", models.CharField(blank=True, max_length=500)),
                ("customer_type", models.CharField(choices=[("private", "Private individual"), ("business", "Business")], max_length=20)),
                ("project_details", models.TextField()),
                ("materials", models.CharField(choices=[("yes", "Yes, please include materials"), ("no", "No, I have the materials"), ("unsure", "Not sure")], max_length=20)),
                ("full_name", models.CharField(max_length=160)), ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(max_length=40)), ("street_address", models.CharField(max_length=240)),
                ("postcode", models.CharField(max_length=20)), ("city", models.CharField(max_length=100)),
                ("additional_information", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("new", "New"), ("reviewing", "Reviewing"), ("quoted", "Quoted"), ("closed", "Closed")], default="new", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ], options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="QuoteRequestAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="electricity/quote_requests/attachments/")),
                ("original_name", models.CharField(max_length=255)), ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("quote_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="electricity.quoterequest")),
            ],
        ),
        migrations.AddField(model_name="adminnotification", name="quote_request", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="admin_notifications", to="electricity.quoterequest")),
    ]
