from django.contrib.auth import authenticate
from django.contrib.auth.hashers import identify_hasher
from django.test import TestCase

from core.models import User


class UserAdminPasswordTests(TestCase):
    """Accounts created or edited in the admin must be able to log in."""

    def setUp(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@bron.test",
            phone="+998900000001",
            password="AdminPass123!",
        )
        self.client.force_login(admin)

    def test_add_user_hashes_password(self):
        response = self.client.post("/admin/core/user/add/", {
            "username": "+998901234567",
            "email": "owner@bron.test",
            "phone": "+998901234567",
            "role": "business_owner",
            "usable_password": "true",
            "password1": "OwnerPass123!",
            "password2": "OwnerPass123!",
        })

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="+998901234567")
        identify_hasher(user.password)
        self.assertEqual(user.role, "business_owner")
        self.assertEqual(
            authenticate(username="+998901234567", password="OwnerPass123!"),
            user,
        )

    def test_change_password_form_hashes_password(self):
        user = User.objects.create_user(
            username="+998907654321",
            email="customer@bron.test",
            phone="+998907654321",
            password="OldPass123!",
        )

        response = self.client.post(f"/admin/core/user/{user.id}/password/", {
            "password1": "NewPass123!",
            "password2": "NewPass123!",
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(authenticate(username=user.username, password="NewPass123!"), user)

    def test_change_page_shows_password_as_read_only(self):
        user = User.objects.create_user(
            username="+998907654322",
            email="viewer@bron.test",
            phone="+998907654322",
            password="ViewPass123!",
        )

        response = self.client.get(f"/admin/core/user/{user.id}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="password"')
        # The hash is shown read-only with a link to the change-password form
        self.assertContains(response, "password/")
