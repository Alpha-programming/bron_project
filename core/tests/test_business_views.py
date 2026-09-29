from django.test import TestCase

from core.models import Business, BusinessView, Category, User
from core.utils.jwt import create_access_token


class BusinessViewCountTests(TestCase):
    """POST /api/businesses/{id}/view counts every request, no deduplication."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="views_owner",
            email="views_owner@bron.test",
            phone="+998901240001",
            password="Pass12345!",
        )
        self.visitor = User.objects.create_user(
            username="views_visitor",
            email="views_visitor@bron.test",
            phone="+998901240002",
            password="Pass12345!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Viewed Spa",
            category=Category.objects.get(slug="spa"),
            address="Tashkent",
            phone="+998901240003",
            is_active=True,
        )
        self.url = f"/api/businesses/{self.business.id}/view"

    @staticmethod
    def auth(user):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}

    def view(self, **extra):
        return self.client.post(self.url, secure=True, **extra)

    def assert_counts(self, responses, start):
        for step, response in enumerate(responses, start=1):
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json(), {"counted": True, "views_count": start + step})

    def test_repeated_views_by_same_user_are_all_counted(self):
        responses = [self.view(**self.auth(self.visitor)) for _ in range(3)]

        self.assert_counts(responses, start=0)
        self.business.refresh_from_db()
        self.assertEqual(self.business.views_count, 3)
        self.assertEqual(
            BusinessView.objects.filter(business=self.business, user=self.visitor).count(),
            3,
        )

    def test_repeated_anonymous_views_are_all_counted(self):
        responses = [self.view(REMOTE_ADDR="10.0.0.7") for _ in range(3)]

        self.assert_counts(responses, start=0)
        rows = BusinessView.objects.filter(business=self.business)
        self.assertEqual(rows.count(), 3)
        self.assertTrue(all(row.user_id is None and row.ip == "10.0.0.7" for row in rows))

    def test_owner_views_are_counted(self):
        responses = [self.view(**self.auth(self.owner)) for _ in range(2)]

        self.assert_counts(responses, start=0)
        self.assertEqual(
            BusinessView.objects.filter(business=self.business, user=self.owner).count(),
            2,
        )

    def test_views_count_continues_from_current_value(self):
        Business.objects.filter(id=self.business.id).update(views_count=41)

        response = self.view()

        self.assertEqual(response.json(), {"counted": True, "views_count": 42})

    def test_invalid_token_is_ignored_and_view_logged_as_anonymous(self):
        response = self.view(HTTP_AUTHORIZATION="Bearer not-a-token", REMOTE_ADDR="10.0.0.8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["views_count"], 1)
        row = BusinessView.objects.get(business=self.business)
        self.assertIsNone(row.user_id)
        self.assertEqual(row.ip, "10.0.0.8")

    def test_forwarded_ip_is_logged(self):
        self.view(HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1", REMOTE_ADDR="10.0.0.1")

        self.assertEqual(BusinessView.objects.get(business=self.business).ip, "203.0.113.5")

    def test_views_show_up_in_business_detail(self):
        self.view()
        self.view()

        response = self.client.get(f"/api/businesses/{self.business.id}", secure=True)

        self.assertEqual(response.json()["views_count"], 2)

    def test_missing_business_returns_404(self):
        response = self.client.post("/api/businesses/999999/view", secure=True)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Business not found"})
        self.assertEqual(BusinessView.objects.count(), 0)

    def test_openapi_documents_view_response(self):
        spec = self.client.get("/api/openapi.json", secure=True).json()

        operation = spec["paths"]["/api/businesses/{business_id}/view"]["post"]
        self.assertEqual(set(operation["responses"]), {"200", "404"})
        self.assertTrue(operation["summary"])
        self.assertIn("separate view", operation["description"])

        schema = spec["components"]["schemas"]["BusinessViewOutSchema"]["properties"]
        self.assertEqual(set(schema), {"counted", "views_count"})
        self.assertTrue(schema["counted"]["description"])
        self.assertTrue(schema["views_count"]["description"])
