import json

from django.test import TestCase

from core.models import Business, Category, User
from core.utils.jwt import create_access_token


class ProfileRoleTests(TestCase):
    """The sidebar shows the business page by the role from the profile."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="role_user",
            email="role_user@bron.test",
            phone="+998901270001",
            password="Pass12345!",
        )
        self.category = Category.objects.get(slug="gym")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.user)}"}

    def role(self, url="/api/users/profile"):
        response = self.client.get(url, secure=True, **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["role"]

    def create_business(self):
        response = self.client.post(
            "/api/businesses/create",
            data=json.dumps({
                "name": "Role Gym",
                "category_id": self.category.id,
                "address": "Tashkent",
                "phone": "+998901270002",
                "email": "role_gym@bron.test",
                "owner_name": "Role Owner",
                "latitude": 41.31,
                "longitude": 69.28,
            }),
            content_type="application/json",
            secure=True,
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return Business.objects.get(id=response.json()["business_id"])

    def test_new_user_is_customer(self):
        self.assertEqual(self.role(), "customer")
        self.assertEqual(self.role("/api/auth/me"), "customer")

    def test_creating_a_business_makes_the_user_its_owner(self):
        self.create_business()

        self.assertEqual(self.role(), "business_owner")
        self.assertEqual(self.role("/api/auth/me"), "business_owner")

    def test_stored_role_stays_customer(self):
        self.create_business()

        # Customer reviews and ratings look the user up by the stored role
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "customer")

    def test_owner_of_hidden_business_is_still_owner(self):
        business = self.create_business()
        business.is_active = False
        business.save()

        self.assertEqual(self.role(), "business_owner")

    def test_deleting_the_last_business_makes_the_user_customer_again(self):
        business = self.create_business()

        response = self.client.delete(
            f"/api/businesses/{business.id}", secure=True, **self.auth
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.assertEqual(self.role(), "customer")

    def test_role_set_by_admin_is_kept(self):
        self.create_business()
        self.user.role = "staff"
        self.user.save()

        self.assertEqual(self.role(), "staff")

    def test_role_is_listed_in_openapi_as_enum(self):
        schema = self.client.get("/api/openapi.json", secure=True).json()
        role = schema["components"]["schemas"]["UserProfileOutSchema"]["properties"]["role"]

        self.assertEqual(role["enum"], ["customer", "business_owner", "admin", "staff"])
