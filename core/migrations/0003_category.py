import django.db.models.deletion
from django.db import migrations, models

LEGACY_CATEGORIES = [
    ("gym", "Gym"),
    ("spa", "Spa"),
    ("salon", "Salon"),
    ("clinic", "Clinic"),
]


def forwards(apps, schema_editor):
    Category = apps.get_model("core", "Category")
    Business = apps.get_model("core", "Business")

    for order, (slug, name) in enumerate(LEGACY_CATEGORIES):
        category, _ = Category.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "order": order},
        )
        Business.objects.filter(category=slug).update(category_fk=category)

    # Any business with an unknown legacy value falls back to the first category
    fallback = Category.objects.order_by("order").first()
    Business.objects.filter(category_fk__isnull=True).update(category_fk=fallback)


def backwards(apps, schema_editor):
    Business = apps.get_model("core", "Business")
    for business in Business.objects.select_related("category_fk"):
        business.category = business.category_fk.slug
        business.save(update_fields=["category"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_alter_business_is_active"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=100, unique=True)),
                ("icon", models.ImageField(blank=True, null=True, upload_to="category_icons/")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "categories",
                "ordering": ["order", "name"],
            },
        ),
        migrations.AddField(
            model_name="business",
            name="category_fk",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="businesses",
                to="core.category",
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="business",
            name="category",
        ),
        migrations.RenameField(
            model_name="business",
            old_name="category_fk",
            new_name="category",
        ),
        migrations.AlterField(
            model_name="business",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="businesses",
                to="core.category",
            ),
        ),
    ]
