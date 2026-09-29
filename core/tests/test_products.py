import json
import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from core.models import Business, Category, Product, User
from core.utils.jwt import create_access_token

TEMP_MEDIA = tempfile.mkdtemp(prefix="bron_test_products_")


def image_bytes(fmt="PNG", color="red"):
    buf = BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format=fmt)
    return buf.getvalue()


def png_upload(name="photo.png", color="red"):
    return SimpleUploadedFile(name, image_bytes("PNG", color), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ProductImageTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@bron.test", phone="+998900000101", password="x"
        )
        self.stranger = User.objects.create_user(
            username="stranger", email="stranger@bron.test", phone="+998900000102", password="x"
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Shop",
            category=Category.objects.get(slug="other"),
            address="Tashkent",
            phone="+998900000103",
            is_active=True,
        )
        self.product = Product.objects.create(
            business=self.business, name="Shampoo", price="95000.00"
        )
        self.url = f"/api/products/{self.product.id}/image"

    def auth(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}

    def upload(self, file, user=None, url=None):
        headers = self.auth(user or self.owner) if user is not False else {}
        return self.client.post(url or self.url, {"image": file}, secure=True, **headers)

    def stored_path(self, name):
        return os.path.join(TEMP_MEDIA, name)

    def test_upload_returns_absolute_url(self):
        response = self.upload(png_upload())

        self.assertEqual(response.status_code, 200, response.content)
        image = response.json()["image"]
        self.assertTrue(image.startswith("http"), image)
        self.assertIn("://testserver/media/products/", image)

        self.product.refresh_from_db()
        self.assertTrue(os.path.exists(self.stored_path(self.product.image.name)))

    def test_image_is_shown_in_detail_and_lists(self):
        self.upload(png_upload())

        detail = self.client.get(f"/api/products/{self.product.id}", secure=True).json()
        listed = self.client.get("/api/products/", secure=True).json()
        by_business = self.client.get(
            f"/api/products/business/{self.business.id}", secure=True
        ).json()

        self.assertTrue(detail["image"].startswith("http"))
        self.assertIn("/media/products/", detail["image"])
        self.assertEqual(listed[0]["image"], detail["image"])
        self.assertEqual(by_business[0]["image"], detail["image"])

    def test_product_without_image_returns_null(self):
        detail = self.client.get(f"/api/products/{self.product.id}", secure=True).json()
        self.assertIsNone(detail["image"])

    def test_wrong_content_type_rejected(self):
        gif = SimpleUploadedFile("photo.gif", image_bytes("GIF"), content_type="image/gif")

        response = self.upload(gif)

        self.assertEqual(response.status_code, 400)
        self.assertIn("JPEG, PNG or WEBP", response.json()["detail"])
        self.product.refresh_from_db()
        self.assertFalse(self.product.image)

    def test_file_larger_than_5_mb_rejected(self):
        big = SimpleUploadedFile(
            "big.png",
            image_bytes() + b"\0" * (5 * 1024 * 1024),
            content_type="image/png",
        )

        response = self.upload(big)

        self.assertEqual(response.status_code, 400)
        self.assertIn("5 MB", response.json()["detail"])

    def test_non_owner_forbidden(self):
        response = self.upload(png_upload(), user=self.stranger)
        self.assertEqual(response.status_code, 403)

        response = self.client.delete(self.url, secure=True, **self.auth(self.stranger))
        self.assertEqual(response.status_code, 403)

    def test_no_token_unauthorized(self):
        response = self.upload(png_upload(), user=False)
        self.assertEqual(response.status_code, 401)

        response = self.client.delete(self.url, secure=True)
        self.assertEqual(response.status_code, 401)

    def test_replacing_removes_old_file(self):
        self.upload(png_upload("first.png", "red"))
        self.product.refresh_from_db()
        old_path = self.stored_path(self.product.image.name)
        self.assertTrue(os.path.exists(old_path))

        response = self.upload(png_upload("second.png", "blue"))

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        new_path = self.stored_path(self.product.image.name)
        self.assertNotEqual(old_path, new_path)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))

    def test_delete_image(self):
        self.upload(png_upload())
        self.product.refresh_from_db()
        path = self.stored_path(self.product.image.name)

        response = self.client.delete(self.url, secure=True, **self.auth(self.owner))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["image"])
        self.assertFalse(os.path.exists(path))
        self.product.refresh_from_db()
        self.assertFalse(self.product.image)

    def test_delete_image_when_none_is_ok(self):
        response = self.client.delete(self.url, secure=True, **self.auth(self.owner))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["image"])

    def test_missing_product_not_found(self):
        missing = "/api/products/999999/image"

        response = self.upload(png_upload(), url=missing)
        self.assertEqual(response.status_code, 404)

        response = self.client.delete(missing, secure=True, **self.auth(self.owner))
        self.assertEqual(response.status_code, 404)

    def test_deleting_product_removes_image_file(self):
        self.upload(png_upload())
        self.product.refresh_from_db()
        path = self.stored_path(self.product.image.name)

        response = self.client.delete(
            f"/api/products/{self.product.id}", secure=True, **self.auth(self.owner)
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())
        self.assertFalse(os.path.exists(path))

    def test_openapi_documents_image_endpoints(self):
        schema = self.client.get("/api/openapi.json", secure=True).json()
        path = schema["paths"]["/api/products/{product_id}/image"]

        self.assertIn("summary", path["post"])
        self.assertIn("multipart/form-data", path["post"]["requestBody"]["content"])
        self.assertIn("5 MB", path["post"]["description"])
        self.assertIn("400", path["post"]["responses"])
        self.assertIn("summary", path["delete"])

        out = schema["components"]["schemas"]["ProductOutSchema"]["properties"]["image"]
        self.assertIn("description", out)


class ProductCreateUpdateTests(TestCase):
    """description is NOT NULL in the database but optional in the API."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="crud_owner", email="crud_owner@bron.test", phone="+998900000111", password="x"
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Crud Shop",
            category=Category.objects.get(slug="other"),
            address="Tashkent",
            phone="+998900000112",
            is_active=True,
        )
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.owner)}"}

    def send(self, method, url, payload):
        return getattr(self.client, method)(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            secure=True,
            **self.headers,
        )

    def create(self, **extra):
        payload = {"business_id": self.business.id, "name": "Soap", "price": "12000.50", **extra}
        return self.send("post", "/api/products/create", payload)

    def test_create_without_description(self):
        response = self.create()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "")
        self.assertEqual(Product.objects.get(id=response.json()["id"]).description, "")

    def test_create_with_null_description(self):
        response = self.create(description=None)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Product.objects.get(id=response.json()["id"]).description, "")

    def test_create_with_description(self):
        response = self.create(description="Olive oil soap")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "Olive oil soap")

    def test_update_null_description_clears_it(self):
        product = Product.objects.create(
            business=self.business, name="Soap", description="Old text", price="1.00"
        )

        response = self.send("put", f"/api/products/{product.id}", {"description": None})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "")
        product.refresh_from_db()
        self.assertEqual(product.description, "")

    def test_update_only_sent_fields(self):
        product = Product.objects.create(
            business=self.business, name="Soap", description="Keep me", price="1.00"
        )

        response = self.send("put", f"/api/products/{product.id}", {"name": "Big soap"})

        self.assertEqual(response.status_code, 200, response.content)
        product.refresh_from_db()
        self.assertEqual(product.name, "Big soap")
        self.assertEqual(product.description, "Keep me")

    def test_update_null_required_field_is_400(self):
        product = Product.objects.create(
            business=self.business, name="Soap", description="Text", price="1.00"
        )

        for field in ("name", "price", "is_active"):
            with self.subTest(field=field):
                response = self.send("put", f"/api/products/{product.id}", {field: None})
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json(), {"detail": f"{field} cannot be null"})

        product.refresh_from_db()
        self.assertEqual((product.name, product.is_active), ("Soap", True))

    def test_openapi_documents_create_and_update(self):
        schema = self.client.get("/api/openapi.json", secure=True).json()

        create = schema["paths"]["/api/products/create"]["post"]
        update = schema["paths"]["/api/products/{product_id}"]["put"]
        for operation in (create, update):
            self.assertTrue(operation["summary"])
            self.assertIn("description", operation["description"])
            self.assertIn("400", operation["responses"])
