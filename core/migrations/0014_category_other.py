from django.db import migrations

OTHER_NAME = "Other"
OTHER_SLUG = "other"

# Large order keeps "Other" at the end of the list
OTHER_ORDER = 1000


def add_other_category(apps, schema_editor):
    Category = apps.get_model("core", "Category")

    by_slug = Category.objects.filter(slug=OTHER_SLUG).first()

    # name and slug are both unique and may sit on two different rows;
    # the name lookup skips the slug row so a clash is always visible here
    candidates = Category.objects.all()
    if by_slug is not None:
        candidates = candidates.exclude(pk=by_slug.pk)
    by_name = (
        candidates.filter(name=OTHER_NAME).first()
        or candidates.filter(name__iexact=OTHER_NAME).first()
    )

    if by_slug is None and by_name is None:
        Category.objects.create(
            name=OTHER_NAME,
            slug=OTHER_SLUG,
            order=OTHER_ORDER,
            is_active=True,
        )
        return

    if by_slug is not None and by_name is not None:
        # Keep the slug row (URLs point at it) and free the name on the other
        max_length = Category._meta.get_field("name").max_length
        suffix = by_name.slug or str(by_name.pk)
        suffix = suffix[:max_length - len(by_name.name) - 3]
        by_name.name = f"{by_name.name} ({suffix})"
        by_name.save(update_fields=["name"])

    category = by_slug or by_name
    category.name = OTHER_NAME
    category.slug = OTHER_SLUG
    category.order = OTHER_ORDER
    category.is_active = True
    category.save(update_fields=["name", "slug", "order", "is_active"])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_businessgallery_sort_order'),
    ]

    # Not removed on rollback: businesses may already reference it (PROTECT)
    operations = [
        migrations.RunPython(add_other_category, migrations.RunPython.noop),
    ]
