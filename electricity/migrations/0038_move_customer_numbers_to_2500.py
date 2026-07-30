from django.db import migrations


def move_customer_numbers(apps, schema_editor):
    CustomerProfile = apps.get_model("electricity", "CustomerProfile")
    customers = list(CustomerProfile.objects.order_by("created_at", "pk"))
    if not customers or min((customer.customer_number or 0) for customer in customers) >= 2500:
        return

    # Clear old values first to avoid unique-number collisions during reassignment.
    CustomerProfile.objects.all().update(customer_number=None)
    for number, customer in enumerate(customers, start=2500):
        customer.customer_number = number
        customer.save(update_fields=["customer_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("electricity", "0037_invoice_customerprofile_customer_number_and_more"),
    ]

    operations = [
        migrations.RunPython(move_customer_numbers, migrations.RunPython.noop),
    ]
