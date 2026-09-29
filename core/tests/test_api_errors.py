import json

from django.test import TestCase
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

from core.models import Business, Category, Product, User
from core.utils.jwt import create_access_token

NOT_JSON = {"detail": "Request body must be JSON"}


class NonJsonBodyTests(TestCase):
    """
    fix_request_files_middleware (PUT/PATCH/DELETE) and OAuth2TokenMiddleware
    (Bearer POST) parse a form body before the view, after which a JSON
    endpoint cannot read request.body: that must be a 400, not a 500.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username="err_owner",
            email="err_owner@bron.test",
            phone="+998901270001",
            password="Pass12345!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Error Shop",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998901270002",
            is_active=True,
        )
        self.product = Product.objects.create(
            business=self.business, name="Shampoo", description="Old", price="95000.00"
        )
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.owner)}"}

    def send(self, method, url, data, content_type=MULTIPART_CONTENT):
        # client.post() encodes a dict itself, put()/patch() need raw bytes
        if content_type == MULTIPART_CONTENT and method != "post":
            data = encode_multipart(BOUNDARY, data)
        return getattr(self.client, method)(
            url, data=data, content_type=content_type, secure=True, **self.headers
        )

    def assert_not_json(self, response):
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(response.json(), NOT_JSON)

    def test_multipart_put_to_product_update(self):
        response = self.send("put", f"/api/products/{self.product.id}", {"name": "New"})

        self.assert_not_json(response)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Shampoo")

    def test_multipart_patch_to_booking_endpoint(self):
        # The body is parsed before the booking is looked up
        response = self.send(
            "patch",
            "/api/bookings/999999/reschedule",
            {"booking_date": "2030-01-01", "start_time": "10:00", "end_time": "11:00"},
        )

        self.assert_not_json(response)

    def test_multipart_post_with_bearer_to_product_create(self):
        response = self.send(
            "post",
            "/api/products/create",
            {"business_id": str(self.business.id), "name": "Soap", "price": "10"},
        )

        self.assert_not_json(response)
        self.assertFalse(Product.objects.filter(name="Soap").exists())

    def test_json_put_still_works(self):
        response = self.send(
            "put",
            f"/api/products/{self.product.id}",
            json.dumps({"name": "New"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], "New")

    def test_urlencoded_put_is_a_parse_error_not_500(self):
        response = self.send(
            "put",
            f"/api/products/{self.product.id}",
            "name=New",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("detail", response.json())
