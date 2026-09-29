import importlib

from django.apps import apps
from django.test import TestCase

from core.models import Business, Category, User

migration = importlib.import_module("core.migrations.0014_category_other")


class AddOtherCategoryMigrationTests(TestCase):
    """
    add_other_category() on databases that already hold a row with the slug
    "other" and/or the name "Other" (both columns are unique).
    """

    def setUp(self):
        # Start from the state before 0014: drop the row it already created
        Category.objects.filter(slug="other").delete()

    def run_migration(self):
        migration.add_other_category(apps, None)

    def assert_single_other(self):
        other = Category.objects.get(slug="other")
        self.assertEqual(other.name, "Other")
        self.assertEqual(other.order, migration.OTHER_ORDER)
        self.assertTrue(other.is_active)
        self.assertEqual(Category.objects.filter(name="Other").count(), 1)
        return other

    def make_business(self, category, phone):
        owner = User.objects.create_user(
            username=f"owner{phone}",
            email=f"owner{phone}@bron.test",
            phone=f"+99890128{phone}",
            password="Pass12345!",
        )
        return Business.objects.create(
            owner=owner,
            name=f"Business {phone}",
            category=category,
            address="Tashkent",
            phone=f"+99890129{phone}",
        )

    def test_creates_other_when_missing(self):
        self.run_migration()

        self.assert_single_other()

    def test_reuses_slug_row_and_moves_it_last(self):
        row = Category.objects.create(name="Misc", slug="other", order=3, is_active=False)

        self.run_migration()

        other = self.assert_single_other()
        self.assertEqual(other.id, row.id)

    def test_reuses_row_with_exact_name(self):
        row = Category.objects.create(name="Other", slug="misc", order=2)

        self.run_migration()

        other = self.assert_single_other()
        self.assertEqual(other.id, row.id)
        self.assertFalse(Category.objects.filter(slug="misc").exists())

    def test_reuses_row_with_name_in_other_case(self):
        row = Category.objects.create(name="OTHER", slug="etc", order=1)

        self.run_migration()

        other = self.assert_single_other()
        self.assertEqual(other.id, row.id)

    def test_slug_and_name_on_different_rows(self):
        slug_row = Category.objects.create(name="Misc", slug="other", order=4)
        name_row = Category.objects.create(name="Other", slug="others", order=5)
        on_slug_row = self.make_business(slug_row, "001")
        on_name_row = self.make_business(name_row, "002")

        self.run_migration()

        other = self.assert_single_other()
        self.assertEqual(other.id, slug_row.id)
        name_row.refresh_from_db()
        self.assertEqual(name_row.name, "Other (others)")
        self.assertEqual(name_row.slug, "others")
        self.assertEqual(name_row.order, 5)
        # Nothing is moved between categories
        on_slug_row.refresh_from_db()
        on_name_row.refresh_from_db()
        self.assertEqual(on_slug_row.category_id, slug_row.id)
        self.assertEqual(on_name_row.category_id, name_row.id)

    def test_slug_row_and_name_in_other_case_on_different_rows(self):
        slug_row = Category.objects.create(name="Misc", slug="other", order=4)
        caps_row = Category.objects.create(name="OTHER", slug="caps", order=5)

        self.run_migration()

        other = self.assert_single_other()
        self.assertEqual(other.id, slug_row.id)
        caps_row.refresh_from_db()
        self.assertEqual(caps_row.name, "OTHER (caps)")

    def test_freed_name_fits_the_column(self):
        Category.objects.create(name="Misc", slug="other")
        long_slug = "x" * 100
        name_row = Category.objects.create(name="Other", slug=long_slug)

        self.run_migration()

        name_row.refresh_from_db()
        max_length = Category._meta.get_field("name").max_length
        self.assertLessEqual(len(name_row.name), max_length)
        self.assertTrue(name_row.name.startswith("Other (x"), name_row.name)
        self.assert_single_other()

    def test_freed_name_uses_id_when_slug_is_blank(self):
        Category.objects.create(name="Misc", slug="other")
        name_row = Category.objects.create(name="Other", slug="tmp")
        # Category.save() fills a blank slug, so blank it the way raw SQL would
        Category.objects.filter(id=name_row.id).update(slug="")

        self.run_migration()

        name_row.refresh_from_db()
        self.assertEqual(name_row.name, f"Other ({name_row.id})")
        self.assert_single_other()

    def test_running_twice_is_harmless(self):
        self.run_migration()
        first = Category.objects.get(slug="other")

        self.run_migration()

        self.assertEqual(self.assert_single_other().id, first.id)
