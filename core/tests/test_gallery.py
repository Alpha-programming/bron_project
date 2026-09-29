import os
import shutil
import tempfile
from io import BytesIO

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from PIL import Image

from core.models import Business, BusinessGallery, Category, User
from core.schemas.business_gallery import BusinessGalleryOutSchema
from core.services.business_gallery import MAX_SORT_ORDER
from core.utils.jwt import create_access_token

MEDIA_PREFIX = "https://testserver/media/business_gallery/"


def make_image(name="photo.png", fmt="PNG", content_type="image/png", color=(200, 30, 30)):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class BusinessGalleryTests(TestCase):

    @classmethod
    def setUpClass(cls):
        # Uploaded files go to a throwaway MEDIA_ROOT, never to media/
        cls.media_root = tempfile.mkdtemp(prefix="bron_gallery_tests_")
        cls.addClassCleanup(shutil.rmtree, cls.media_root, ignore_errors=True)
        cls.enterClassContext(override_settings(MEDIA_ROOT=cls.media_root))
        super().setUpClass()

    def setUp(self):
        self.owner = User.objects.create_user(
            username="gallery_owner",
            email="gallery_owner@bron.test",
            phone="+998901230001",
            password="Pass12345!",
        )
        self.stranger = User.objects.create_user(
            username="gallery_stranger",
            email="gallery_stranger@bron.test",
            phone="+998901230002",
            password="Pass12345!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Gallery Gym",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998901230003",
            is_active=True,
        )
        self.owner_auth = self.auth(self.owner)

    # --- helpers ---

    @staticmethod
    def auth(user):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}

    def upload(self, image=None, **extra):
        return self.client.post(
            f"/api/business-gallery/upload/{self.business.id}",
            {"image": image or make_image()},
            secure=True,
            **(extra or self.owner_auth),
        )

    def put(self, image_id, data, **extra):
        # A real multipart PUT, the way browsers and Swagger UI send it
        return self.client.put(
            f"/api/business-gallery/{image_id}",
            data=encode_multipart(BOUNDARY, data),
            content_type=MULTIPART_CONTENT,
            secure=True,
            **extra,
        )

    def stored_image(self, sort_order=0, name="stored.png"):
        return BusinessGallery.objects.create(
            business=self.business,
            image=make_image(name=name),
            sort_order=sort_order,
        )

    # --- upload ---

    def test_uploads_get_increasing_sort_order(self):
        orders = []
        for _ in range(3):
            response = self.upload()
            self.assertEqual(response.status_code, 200, response.content)
            orders.append(response.json()["sort_order"])

        self.assertEqual(orders, [0, 1, 2])

    def test_upload_appends_after_current_max(self):
        self.stored_image(sort_order=7)
        self.stored_image(sort_order=3)

        response = self.upload()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sort_order"], 8)

    def test_upload_after_max_sort_order_stays_in_range(self):
        # A PUT may set the largest value PostgreSQL int accepts; the next
        # upload must not go past it (DataError -> 500 there)
        self.stored_image(sort_order=MAX_SORT_ORDER)

        response = self.upload()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sort_order"], MAX_SORT_ORDER)
        self.assertEqual(
            BusinessGallery.objects.get(id=response.json()["id"]).sort_order,
            MAX_SORT_ORDER,
        )

    def test_put_max_sort_order_then_upload(self):
        image = self.stored_image(sort_order=0)
        response = self.put(image.id, {"sort_order": str(MAX_SORT_ORDER)}, **self.owner_auth)
        self.assertEqual(response.status_code, 200, response.content)

        response = self.upload()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sort_order"], MAX_SORT_ORDER)
        # Equal sort_order falls back to id: the new picture is still last
        listed = self.client.get(
            f"/api/business-gallery/business/{self.business.id}", secure=True
        ).json()
        self.assertEqual(listed[-1]["id"], response.json()["id"])

    def test_upload_returns_absolute_url_and_stores_under_temp_media(self):
        response = self.upload()

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data["image"].startswith(MEDIA_PREFIX), data["image"])
        image = BusinessGallery.objects.get(id=data["id"])
        self.assertTrue(
            os.path.normcase(image.image.path).startswith(os.path.normcase(self.media_root)),
            image.image.path,
        )

    def test_upload_rejects_wrong_type(self):
        response = self.upload(make_image(name="anim.gif", fmt="GIF", content_type="image/gif"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(BusinessGallery.objects.count(), 0)

    # --- list ---

    def test_list_ordered_by_sort_order_then_id(self):
        third = self.stored_image(sort_order=2)
        first = self.stored_image(sort_order=0)
        second_a = self.stored_image(sort_order=1)
        second_b = self.stored_image(sort_order=1)

        response = self.client.get(
            f"/api/business-gallery/business/{self.business.id}",
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()],
            [first.id, second_a.id, second_b.id, third.id],
        )
        self.assertEqual(
            set(response.json()[0]),
            {"id", "business_id", "image", "sort_order", "created_at"},
        )

    # --- PUT /{image_id} ---

    def test_put_replaces_image_and_removes_old_file(self):
        image = self.stored_image(sort_order=4)
        old_name = image.image.name
        self.assertTrue(default_storage.exists(old_name))

        response = self.put(image.id, {"image": make_image(name="new.png", color=(0, 0, 255))}, **self.owner_auth)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        image.refresh_from_db()
        self.assertNotEqual(image.image.name, old_name)
        self.assertFalse(default_storage.exists(old_name))
        self.assertTrue(default_storage.exists(image.image.name))
        self.assertTrue(data["image"].startswith(MEDIA_PREFIX), data["image"])
        self.assertTrue(data["image"].endswith(image.image.url))
        # Replacing the picture keeps its position
        self.assertEqual(data["sort_order"], 4)
        self.assertEqual(image.sort_order, 4)

    def test_put_sort_order_only(self):
        image = self.stored_image(sort_order=0)
        name = image.image.name

        response = self.put(image.id, {"sort_order": "5"}, **self.owner_auth)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sort_order"], 5)
        image.refresh_from_db()
        self.assertEqual(image.sort_order, 5)
        self.assertEqual(image.image.name, name)
        self.assertTrue(default_storage.exists(name))

    def test_put_image_and_sort_order(self):
        image = self.stored_image(sort_order=0)
        old_name = image.image.name

        response = self.put(
            image.id,
            {"image": make_image(name="both.png"), "sort_order": "2"},
            **self.owner_auth,
        )

        self.assertEqual(response.status_code, 200, response.content)
        image.refresh_from_db()
        self.assertEqual(image.sort_order, 2)
        self.assertNotEqual(image.image.name, old_name)
        self.assertFalse(default_storage.exists(old_name))

    def test_put_sort_order_changes_list_order(self):
        first = self.stored_image(sort_order=0)
        second = self.stored_image(sort_order=1)

        self.put(first.id, {"sort_order": "9"}, **self.owner_auth)

        response = self.client.get(
            f"/api/business-gallery/business/{self.business.id}",
            secure=True,
        )
        self.assertEqual([item["id"] for item in response.json()], [second.id, first.id])

    def test_put_without_fields_returns_400(self):
        image = self.stored_image()

        response = self.put(image.id, {}, **self.owner_auth)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Provide image or sort_order"})

    def test_put_invalid_sort_order_returns_422(self):
        image = self.stored_image(sort_order=3)

        for value in ("", "-1", "abc", "1.5", "99999999999"):
            with self.subTest(value=value):
                response = self.put(image.id, {"sort_order": value}, **self.owner_auth)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"][0]["loc"][-1], "sort_order")

        image.refresh_from_db()
        self.assertEqual(image.sort_order, 3)

    def test_put_wrong_file_type_returns_400_and_keeps_old_file(self):
        image = self.stored_image()
        old_name = image.image.name

        response = self.put(
            image.id,
            {"image": make_image(name="anim.gif", fmt="GIF", content_type="image/gif")},
            **self.owner_auth,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only JPEG, PNG or WEBP images are allowed")
        image.refresh_from_db()
        self.assertEqual(image.image.name, old_name)
        self.assertTrue(default_storage.exists(old_name))

    def test_put_too_large_file_returns_400(self):
        image = self.stored_image()
        big = SimpleUploadedFile("big.png", b"\0" * (5 * 1024 * 1024 + 1), content_type="image/png")

        response = self.put(image.id, {"image": big}, **self.owner_auth)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Image must be smaller than 5 MB")

    def test_put_accepts_jpeg_and_webp(self):
        image = self.stored_image()

        for name, fmt, content_type in (
            ("photo.jpg", "JPEG", "image/jpeg"),
            ("photo.webp", "WEBP", "image/webp"),
        ):
            with self.subTest(fmt=fmt):
                response = self.put(
                    image.id,
                    {"image": make_image(name=name, fmt=fmt, content_type=content_type)},
                    **self.owner_auth,
                )
                self.assertEqual(response.status_code, 200, response.content)
                self.assertTrue(response.json()["image"].endswith(name.rsplit(".", 1)[1]))

    def test_put_malformed_multipart_returns_400(self):
        image = self.stored_image()

        response = self.client.put(
            f"/api/business-gallery/{image.id}",
            data=b"garbage",
            content_type="multipart/form-data",  # no boundary
            secure=True,
            **self.owner_auth,
        )

        self.assertEqual(response.status_code, 400)

    def test_put_sort_order_as_urlencoded_form(self):
        image = self.stored_image()

        response = self.client.put(
            f"/api/business-gallery/{image.id}",
            data="sort_order=6",
            content_type="application/x-www-form-urlencoded",
            secure=True,
            **self.owner_auth,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sort_order"], 6)

    def test_files_middleware_order(self):
        middleware = settings.MIDDLEWARE
        files = middleware.index("ninja.compatibility.files.fix_request_files_middleware")

        # Security/CORS must wrap it so its 400 responses get their headers
        self.assertGreater(files, middleware.index("django.middleware.security.SecurityMiddleware"))
        self.assertGreater(files, middleware.index("corsheaders.middleware.CorsMiddleware"))
        # OAuth2TokenMiddleware reads request.POST; parsing the PUT body
        # after that fails with "cannot set upload handlers"
        self.assertLess(files, middleware.index("oauth2_provider.middleware.OAuth2TokenMiddleware"))

    def test_malformed_multipart_put_keeps_cors_headers(self):
        image = self.stored_image()
        origin = "https://front.example.com"

        response = self.client.put(
            f"/api/business-gallery/{image.id}",
            data=b"garbage",
            content_type="multipart/form-data",  # no boundary
            secure=True,
            HTTP_ORIGIN=origin,
            **self.owner_auth,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)

    def test_multipart_put_with_origin_still_works(self):
        image = self.stored_image(sort_order=0)
        origin = "https://front.example.com"

        response = self.put(image.id, {"sort_order": "3"}, HTTP_ORIGIN=origin, **self.owner_auth)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sort_order"], 3)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)

    def test_put_by_non_owner_returns_403(self):
        image = self.stored_image(sort_order=1)

        response = self.put(image.id, {"sort_order": "0"}, **self.auth(self.stranger))

        self.assertEqual(response.status_code, 403)
        image.refresh_from_db()
        self.assertEqual(image.sort_order, 1)

    def test_put_missing_image_returns_404(self):
        response = self.put(999999, {"sort_order": "0"}, **self.owner_auth)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Image not found"})

    def test_put_without_token_returns_401(self):
        image = self.stored_image()

        response = self.put(image.id, {"sort_order": "0"})

        self.assertEqual(response.status_code, 401)

    # --- DELETE /{image_id} ---

    def test_delete_removes_record_and_file(self):
        image = self.stored_image()
        name = image.image.name

        response = self.client.delete(
            f"/api/business-gallery/{image.id}",
            secure=True,
            **self.owner_auth,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Image deleted successfully"})
        self.assertFalse(BusinessGallery.objects.filter(id=image.id).exists())
        self.assertFalse(default_storage.exists(name))

    # --- schema / Swagger ---

    def test_out_schema_has_sort_order(self):
        self.assertIn("sort_order", BusinessGalleryOutSchema.model_fields)

    def test_openapi_documents_gallery_endpoints(self):
        spec = self.client.get("/api/openapi.json", secure=True).json()

        put = spec["paths"]["/api/business-gallery/{image_id}"]["put"]
        form = put["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"]
        self.assertEqual(form["image"]["format"], "binary")
        self.assertIn("5 MB", form["image"]["description"])
        self.assertEqual(form["sort_order"]["type"], "integer")
        self.assertEqual(set(put["responses"]), {"200", "400", "401", "403", "404"})
        self.assertTrue(put["summary"])

        upload = spec["paths"]["/api/business-gallery/upload/{business_id}"]["post"]
        self.assertIn("20 images", upload["description"])
        self.assertIn("5 MB", upload["description"])

        out = spec["components"]["schemas"]["BusinessGalleryOutSchema"]["properties"]
        self.assertIn("sort_order", out)
        self.assertTrue(out["sort_order"]["description"])
