from datetime import date

from django.test import TestCase

from core.models import BlockedDate, Business, Category, User

URL = "/api/blocked-dates/check"


class BlockedDateCheckTests(TestCase):

    def setUp(self):
        owner = User.objects.create_user(
            username="blocked_owner",
            email="blocked_owner@bron.test",
            phone="+998901120001",
            password="Pass12345!",
            role="business_owner",
        )
        self.business = Business.objects.create(
            owner=owner,
            name="Blocked Test Spa",
            category=Category.objects.get(slug="spa"),
            address="Tashkent",
            phone="+998901120002",
            is_active=True,
        )
        BlockedDate.objects.create(
            business=self.business, date=date(2026, 10, 5), reason="Holiday"
        )
        BlockedDate.objects.create(
            business=self.business, date=date(2026, 10, 6), reason=None
        )

    def check(self, **params):
        return self.client.get(URL, params, secure=True)

    def test_blocked_date_returns_reason(self):
        response = self.check(business_id=self.business.id, date="2026-10-05")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "business_id": self.business.id,
            "date": "2026-10-05",
            "is_blocked": True,
            "reason": "Holiday",
        })

    def test_blocked_date_without_reason(self):
        data = self.check(business_id=self.business.id, date="2026-10-06").json()

        self.assertTrue(data["is_blocked"])
        self.assertIsNone(data["reason"])

    def test_free_date_is_not_blocked(self):
        response = self.check(business_id=self.business.id, date="2026-10-07")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "business_id": self.business.id,
            "date": "2026-10-07",
            "is_blocked": False,
            "reason": None,
        })

    def test_response_keys(self):
        data = self.check(business_id=self.business.id, date="2026-10-05").json()

        self.assertEqual(set(data), {"business_id", "date", "is_blocked", "reason"})

    def test_block_of_another_business_does_not_leak(self):
        other = Business.objects.create(
            owner=self.business.owner,
            name="Other Spa",
            category=self.business.category,
            address="Tashkent",
            phone="+998901120003",
        )

        data = self.check(business_id=other.id, date="2026-10-05").json()

        self.assertFalse(data["is_blocked"])

    def test_unknown_business_is_not_blocked(self):
        response = self.check(business_id=999999, date="2026-10-05")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_blocked"])

    def test_old_target_date_param_is_rejected(self):
        response = self.check(business_id=self.business.id, target_date="2026-10-05")

        self.assertEqual(response.status_code, 422)

    def test_missing_date_is_rejected(self):
        response = self.check(business_id=self.business.id)

        self.assertEqual(response.status_code, 422)

    def test_missing_business_id_is_rejected(self):
        response = self.check(date="2026-10-05")

        self.assertEqual(response.status_code, 422)

    def test_malformed_date_is_rejected(self):
        response = self.check(business_id=self.business.id, date="05.10.2026")

        self.assertEqual(response.status_code, 422)

    def test_openapi_documents_date_param_and_response(self):
        schema = self.client.get("/api/openapi.json", secure=True).json()

        operation = schema["paths"]["/api/blocked-dates/check"]["get"]
        self.assertTrue(operation["summary"])
        params = {p["name"]: p for p in operation["parameters"]}
        self.assertEqual(set(params), {"business_id", "date"})
        self.assertTrue(params["date"]["required"])
        self.assertEqual(params["date"]["schema"]["format"], "date")
        self.assertTrue(params["date"].get("description"))

        out = schema["components"]["schemas"]["BlockedCheckOutSchema"]
        self.assertEqual(set(out["properties"]), {"business_id", "date", "is_blocked", "reason"})
        for field in out["properties"].values():
            self.assertTrue(field.get("description"))
