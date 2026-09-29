import json

from django.test import TestCase

from core.models import Business, Category, User
from core.services.category import get_active_categories, get_category_by_slug
from core.utils.jwt import create_access_token


class OtherCategoryTests(TestCase):
    """Migration 0014 adds the catch-all "Other" category."""

    def test_list_contains_other(self):
        response = self.client.get("/api/categories/", secure=True)

        self.assertEqual(response.status_code, 200)
        others = [item for item in response.json() if item["slug"] == "other"]
        self.assertEqual(len(others), 1)
        self.assertEqual(others[0]["name"], "Other")

    def test_other_is_listed_last(self):
        response = self.client.get("/api/categories/", secure=True)

        self.assertEqual(response.json()[-1]["slug"], "other")

    def test_list_query_has_explicit_order_by(self):
        # The Count annotation adds GROUP BY, and Django then drops
        # Meta.ordering: SQLite still returns id order, PostgreSQL does not
        sql = str(get_active_categories().query)

        self.assertIn(
            'ORDER BY "core_category"."order" ASC, "core_category"."name" ASC',
            sql,
        )

    def test_detail_query_keeps_business_count(self):
        self.assertEqual(get_category_by_slug("other").business_count, 0)

    def test_list_sorted_by_order_then_name(self):
        Category.objects.create(name="Zoo", slug="zoo", order=999)
        Category.objects.create(name="Aquarium", slug="aquarium", order=999)
        Category.objects.create(name="Hidden", slug="hidden", order=5, is_active=False)

        response = self.client.get("/api/categories/", secure=True)

        slugs = [item["slug"] for item in response.json()]
        self.assertEqual(slugs[-3:], ["aquarium", "zoo", "other"])
        self.assertNotIn("hidden", slugs)
        expected = list(
            Category.objects.filter(is_active=True)
            .order_by("order", "name")
            .values_list("slug", flat=True)
        )
        self.assertEqual(slugs, expected)

    def test_other_detail(self):
        response = self.client.get("/api/categories/other", secure=True)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Other")
        self.assertEqual(data["slug"], "other")
        self.assertEqual(data["id"], Category.objects.get(slug="other").id)

    def test_business_can_be_created_in_other(self):
        user = User.objects.create_user(
            username="other_owner",
            email="other_owner@bron.test",
            phone="+998901250001",
            password="Pass12345!",
        )
        other = Category.objects.get(slug="other")

        response = self.client.post(
            "/api/businesses/create",
            data=json.dumps({
                "name": "Misc Studio",
                "category_id": other.id,
                "address": "Tashkent",
                "phone": "+998901250002",
                "email": "misc@bron.test",
                "owner_name": "Misc Owner",
            }),
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        business = Business.objects.get(id=response.json()["business_id"])
        self.assertEqual(business.category, other)
        self.assertEqual(business.owner, user)
