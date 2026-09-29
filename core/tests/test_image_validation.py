import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from ninja.errors import HttpError
from PIL import Image

from core.models import Business, BusinessGallery, Category, Product, Service, User
from core.utils.jwt import create_access_token
from core.utils.validators import validate_image

WRONG_TYPE = "Only JPEG, PNG or WEBP images are allowed"

HTML = b"<!doctype html><html><body><script>alert(document.cookie)</script></body></html>"
SVG = (
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">'
    b"<script>alert(1)</script></svg>"
)


def image_bytes(fmt="PNG", color=(200, 30, 30)):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(buffer, format=fmt)
    return buffer.getvalue()


def upload(name, content, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


class ValidateImageTests(SimpleTestCase):
    """validate_image() on its own, as every upload service calls it."""

    def assert_rejected(self, file, message=WRONG_TYPE):
        with self.assertRaises(HttpError) as ctx:
            validate_image(file)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(str(ctx.exception), message)

    def test_html_sent_as_png_rejected(self):
        self.assert_rejected(upload("evil.png", HTML, "image/png"))

    def test_svg_rejected_by_content_type_and_by_content(self):
        self.assert_rejected(upload("logo.svg", SVG, "image/svg+xml"))
        self.assert_rejected(upload("logo.png", SVG, "image/png"))

    def test_gif_rejected_even_when_labelled_png(self):
        self.assert_rejected(upload("anim.gif", image_bytes("GIF"), "image/gif"))
        self.assert_rejected(upload("anim.png", image_bytes("GIF"), "image/png"))

    def test_truncated_or_empty_image_rejected(self):
        self.assert_rejected(upload("cut.png", image_bytes("PNG")[:30], "image/png"))
        self.assert_rejected(upload("empty.png", b"", "image/png"))

    def test_oversized_rejected(self):
        big = upload("big.png", image_bytes() + b"\0" * (5 * 1024 * 1024), "image/png")
        self.assert_rejected(big, "Image must be smaller than 5 MB")

    def test_custom_limit(self):
        file = upload("p.png", image_bytes() + b"\0" * (1024 * 1024), "image/png")

        with self.assertRaises(HttpError) as ctx:
            validate_image(file, max_mb=1)

        self.assertEqual(str(ctx.exception), "Image must be smaller than 1 MB")

    def test_extension_follows_real_format(self):
        cases = (
            ("evil.html", "PNG", "image/png", "evil.png"),
            ("photo.png", "JPEG", "image/jpeg", "photo.jpg"),
            ("photo.jpeg", "JPEG", "image/jpeg", "photo.jpg"),
            ("photo.PNG", "PNG", "image/png", "photo.png"),
            ("pic.webp", "WEBP", "image/webp", "pic.webp"),
            ("no_extension", "PNG", "image/png", "no_extension.png"),
            ("archive.tar.gz", "WEBP", "image/webp", "archive.tar.webp"),
        )
        for name, fmt, content_type, expected in cases:
            with self.subTest(name=name, fmt=fmt):
                file = upload(name, image_bytes(fmt), content_type)
                validate_image(file)
                self.assertEqual(file.name, expected)

    def test_jpg_alias_content_type_accepted(self):
        file = upload("photo.jpg", image_bytes("JPEG"), "image/jpg")

        validate_image(file)

        self.assertEqual(file.name, "photo.jpg")

    def test_file_is_rewound_for_saving(self):
        content = image_bytes("PNG")
        file = upload("photo.png", content, "image/png")
        file.read()

        validate_image(file)

        self.assertEqual(file.tell(), 0)
        self.assertEqual(file.read(), content)

    def test_temporary_uploaded_file(self):
        # Large uploads (and admin uploads over FILE_UPLOAD_MAX_MEMORY_SIZE)
        # arrive as TemporaryUploadedFile instead of an in-memory file
        content = image_bytes("PNG")
        file = TemporaryUploadedFile("evil.html", "image/png", len(content), None)
        self.addCleanup(file.close)
        file.write(content)

        validate_image(file)

        self.assertEqual(file.name, "evil.png")
        self.assertEqual(file.read(), content)

        bad = TemporaryUploadedFile("evil.png", "image/png", len(HTML), None)
        self.addCleanup(bad.close)
        bad.write(HTML)
        self.assert_rejected(bad)


class ImageUploadEndpointTests(TestCase):
    """The content check through the real upload endpoints."""

    def setUp(self):
        # Fresh MEDIA_ROOT per test, so "nothing was stored" checks are exact
        self.media_root = tempfile.mkdtemp(prefix="bron_image_validation_")
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.media_root)
        media.enable()
        self.addCleanup(media.disable)

        self.owner = User.objects.create_user(
            username="img_owner",
            email="img_owner@bron.test",
            phone="+998901260001",
            password="Pass12345!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Image Shop",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998901260002",
            is_active=True,
        )
        self.product = Product.objects.create(
            business=self.business, name="Shampoo", price="95000.00"
        )
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(self.owner)}"}

    def post(self, url, file):
        return self.client.post(url, {"image": file}, secure=True, **self.headers)

    def stored_files(self, folder):
        path = os.path.join(self.media_root, folder)
        return os.listdir(path) if os.path.isdir(path) else []

    # --- products ---

    def test_product_html_as_png_rejected_and_nothing_stored(self):
        response = self.post(
            f"/api/products/{self.product.id}/image", upload("evil.png", HTML, "image/png")
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": WRONG_TYPE})
        self.product.refresh_from_db()
        self.assertFalse(self.product.image)
        self.assertEqual(self.stored_files("products"), [])

    def test_product_svg_and_gif_rejected(self):
        for file in (
            upload("logo.svg", SVG, "image/svg+xml"),
            upload("logo.png", SVG, "image/png"),
            upload("anim.png", image_bytes("GIF"), "image/png"),
        ):
            with self.subTest(name=file.name, content_type=file.content_type):
                response = self.post(f"/api/products/{self.product.id}/image", file)
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.stored_files("products"), [])

    def test_product_real_png_named_html_stored_as_png(self):
        response = self.post(
            f"/api/products/{self.product.id}/image",
            upload("evil.html", image_bytes("PNG"), "image/png"),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.product.refresh_from_db()
        self.assertTrue(self.product.image.name.startswith("products/evil"), self.product.image.name)
        self.assertTrue(self.product.image.name.endswith(".png"), self.product.image.name)
        self.assertTrue(response.json()["image"].endswith(".png"))
        self.assertTrue(default_storage.exists(self.product.image.name))
        self.assertFalse(any(name.endswith(".html") for name in self.stored_files("products")))

    def test_product_oversized_rejected(self):
        big = upload("big.png", image_bytes() + b"\0" * (5 * 1024 * 1024), "image/png")

        response = self.post(f"/api/products/{self.product.id}/image", big)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Image must be smaller than 5 MB"})

    # --- gallery ---

    def test_gallery_upload_svg_rejected(self):
        response = self.post(
            f"/api/business-gallery/upload/{self.business.id}",
            upload("logo.png", SVG, "image/png"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": WRONG_TYPE})
        self.assertEqual(BusinessGallery.objects.count(), 0)
        self.assertEqual(self.stored_files("business_gallery"), [])

    def test_gallery_upload_jpeg_gets_jpg_extension(self):
        response = self.post(
            f"/api/business-gallery/upload/{self.business.id}",
            upload("photo.png", image_bytes("JPEG"), "image/jpeg"),
        )

        self.assertEqual(response.status_code, 200, response.content)
        image = BusinessGallery.objects.get(id=response.json()["id"])
        self.assertTrue(image.image.name.endswith(".jpg"), image.image.name)
        self.assertTrue(response.json()["image"].endswith(".jpg"))

    def test_gallery_put_html_rejected_and_keeps_old_file(self):
        stored = BusinessGallery.objects.create(
            business=self.business,
            image=upload("old.png", image_bytes("PNG"), "image/png"),
        )
        old_name = stored.image.name

        response = self.client.put(
            f"/api/business-gallery/{stored.id}",
            data=encode_multipart(BOUNDARY, {"image": upload("new.png", HTML, "image/png")}),
            content_type=MULTIPART_CONTENT,
            secure=True,
            **self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": WRONG_TYPE})
        stored.refresh_from_db()
        self.assertEqual(stored.image.name, old_name)
        self.assertTrue(default_storage.exists(old_name))

    def test_gallery_put_real_webp_named_svg_stored_as_webp(self):
        stored = BusinessGallery.objects.create(
            business=self.business,
            image=upload("old.png", image_bytes("PNG"), "image/png"),
        )

        response = self.client.put(
            f"/api/business-gallery/{stored.id}",
            data=encode_multipart(
                BOUNDARY, {"image": upload("pic.svg", image_bytes("WEBP"), "image/webp")}
            ),
            content_type=MULTIPART_CONTENT,
            secure=True,
            **self.headers,
        )

        self.assertEqual(response.status_code, 200, response.content)
        stored.refresh_from_db()
        self.assertTrue(stored.image.name.endswith(".webp"), stored.image.name)

    # --- other callers of validate_image keep working ---

    def test_avatar_logo_and_service_image_accept_real_images(self):
        service = Service.objects.create(
            business=self.business,
            title="Training",
            description="Personal training",
            category="fitness",
            duration=60,
            price="100000.00",
        )

        cases = (
            ("/api/users/profile/avatar", self.owner, "avatar"),
            (f"/api/businesses/{self.business.id}/logo", self.business, "logo"),
            (f"/api/services/{service.id}/image", service, "image"),
        )
        for url, obj, field in cases:
            with self.subTest(url=url):
                response = self.post(url, upload("pic.html", image_bytes("JPEG"), "image/jpg"))
                self.assertEqual(response.status_code, 200, response.content)
                obj.refresh_from_db()
                name = getattr(obj, field).name
                self.assertTrue(name.endswith(".jpg"), name)
                self.assertTrue(default_storage.exists(name))

    def test_avatar_logo_and_service_image_reject_html(self):
        service = Service.objects.create(
            business=self.business,
            title="Training",
            description="Personal training",
            category="fitness",
            duration=60,
            price="100000.00",
        )

        for url in (
            "/api/users/profile/avatar",
            f"/api/businesses/{self.business.id}/logo",
            f"/api/services/{service.id}/image",
        ):
            with self.subTest(url=url):
                response = self.post(url, upload("pic.png", HTML, "image/png"))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"detail": WRONG_TYPE})
