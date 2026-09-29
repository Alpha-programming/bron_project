import json

from django.test import TestCase

from core.models import User
from core.utils.jwt import create_access_token

URL = "/api/users/profile/notifications"
KEYS = {"push", "email", "bookingReminder", "promotions"}


class NotificationSettingsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="notify_user",
            email="notify@bron.test",
            phone="+998901110001",
            password="Pass12345!",
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.user)}"}

    def get(self, **extra):
        return self.client.get(URL, secure=True, **extra)

    def put(self, body, **extra):
        return self.client.put(
            URL,
            data=json.dumps(body),
            content_type="application/json",
            secure=True,
            **extra,
        )

    def test_defaults_for_new_user(self):
        response = self.get(**self.auth)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "push": True,
            "email": True,
            "bookingReminder": True,
            "promotions": False,
        })

    def test_booking_reminder_key_is_camel_case(self):
        data = self.get(**self.auth).json()

        self.assertEqual(set(data), KEYS)
        self.assertIn("bookingReminder", data)
        self.assertNotIn("booking_reminder", data)

    def test_put_updates_only_sent_keys(self):
        response = self.put({"promotions": True, "push": False}, **self.auth)

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.notify_promotions)
        self.assertFalse(self.user.notify_push)
        # Untouched keys keep their values
        self.assertTrue(self.user.notify_email)
        self.assertTrue(self.user.notify_booking_reminder)

    def test_put_accepts_camel_case_booking_reminder(self):
        response = self.put({"bookingReminder": False}, **self.auth)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["bookingReminder"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.notify_booking_reminder)

    def test_put_returns_full_object_and_get_shows_new_values(self):
        expected = {
            "push": True,
            "email": False,
            "bookingReminder": True,
            "promotions": True,
        }

        response = self.put({"email": False, "promotions": True}, **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

        self.assertEqual(self.get(**self.auth).json(), expected)

    def test_null_values_are_ignored(self):
        self.user.notify_promotions = True
        self.user.save(update_fields=["notify_promotions"])

        response = self.put(
            {"push": None, "email": None, "bookingReminder": None, "promotions": None},
            **self.auth,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "push": True,
            "email": True,
            "bookingReminder": True,
            "promotions": True,
        })

    def test_empty_body_changes_nothing(self):
        response = self.put({}, **self.auth)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["promotions"], False)

    def test_non_boolean_value_is_rejected(self):
        response = self.put({"push": "maybe"}, **self.auth)

        self.assertEqual(response.status_code, 422)
        self.user.refresh_from_db()
        self.assertTrue(self.user.notify_push)

    def test_settings_are_per_user(self):
        other = User.objects.create_user(
            username="notify_other",
            email="notify_other@bron.test",
            phone="+998901110002",
            password="Pass12345!",
        )

        self.put({"push": False}, **self.auth)

        other.refresh_from_db()
        self.assertTrue(other.notify_push)

    def test_get_requires_token(self):
        self.assertEqual(self.get().status_code, 401)

    def test_put_requires_token(self):
        response = self.put({"push": False})

        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertTrue(self.user.notify_push)

    def test_invalid_token_is_rejected(self):
        response = self.get(HTTP_AUTHORIZATION="Bearer not-a-token")

        self.assertEqual(response.status_code, 401)

    def test_openapi_documents_camel_case_schema(self):
        schema = self.client.get("/api/openapi.json", secure=True).json()

        path = schema["paths"]["/api/users/profile/notifications"]
        self.assertIn("get", path)
        self.assertIn("put", path)
        self.assertTrue(path["get"]["summary"])
        self.assertTrue(path["put"]["summary"])

        components = schema["components"]["schemas"]
        out = components["NotificationSettingsSchema"]
        self.assertEqual(set(out["properties"]), KEYS)
        self.assertEqual(set(out["required"]), KEYS)
        self.assertTrue(out["properties"]["bookingReminder"]["description"])

        update = components["NotificationSettingsUpdateSchema"]
        self.assertEqual(set(update["properties"]), KEYS)
        self.assertFalse(update.get("required"))
