import json

from django.test import TestCase

from core.models import Business, Category, User
from core.utils.jwt import create_access_token


class BusinessVisibilityTests(TestCase):
    """A new business is public right away; only an admin can hide it."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="visible_owner",
            email="visible_owner@bron.test",
            phone="+998901260001",
            password="Pass12345!",
        )
        self.category = Category.objects.get(slug="gym")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.owner)}"}

    def create_business(self):
        response = self.client.post(
            "/api/businesses/create",
            data=json.dumps({
                "name": "Visible Gym",
                "category_id": self.category.id,
                "address": "Tashkent",
                "phone": "+998901260002",
                "email": "visible@bron.test",
                "owner_name": "Visible Owner",
                "latitude": 41.31,
                "longitude": 69.28,
            }),
            content_type="application/json",
            secure=True,
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return Business.objects.get(id=response.json()["business_id"])

    def public_ids(self):
        response = self.client.get("/api/businesses/", secure=True)
        self.assertEqual(response.status_code, 200, response.content)
        return [item["id"] for item in response.json()]

    def test_created_business_is_public_without_approval(self):
        business = self.create_business()

        self.assertTrue(business.is_active)
        self.assertIn(business.id, self.public_ids())

        detail = self.client.get(f"/api/businesses/{business.id}", secure=True).json()
        self.assertEqual(detail["status"], "approved")

        categories = self.client.get("/api/categories/", secure=True).json()
        gym = next(item for item in categories if item["slug"] == "gym")
        self.assertEqual(gym["business_count"], 1)

    def test_business_hidden_by_admin_leaves_public_list(self):
        business = self.create_business()
        Business.objects.filter(id=business.id).update(is_active=False)

        self.assertNotIn(business.id, self.public_ids())

        mine = self.client.get("/api/businesses/my", secure=True, **self.auth).json()
        self.assertEqual([(item["id"], item["status"]) for item in mine], [(business.id, "pending")])
