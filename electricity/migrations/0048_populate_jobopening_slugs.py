from django.db import migrations
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    JobOpening = apps.get_model("electricity", "JobOpening")
    used = set(JobOpening.objects.exclude(slug="").values_list("slug", flat=True))
    for job in JobOpening.objects.filter(slug="").order_by("pk"):
        base = slugify(job.title) or f"job-{job.pk}"
        candidate = base
        counter = 2
        while candidate in used:
            candidate = f"{base}-{counter}"
            counter += 1
        job.slug = candidate
        job.save(update_fields=["slug"])
        used.add(candidate)


class Migration(migrations.Migration):
    dependencies = [("electricity", "0047_jobopening_about_role_jobopening_hero_image_and_more")]

    operations = [migrations.RunPython(populate_slugs, migrations.RunPython.noop)]
