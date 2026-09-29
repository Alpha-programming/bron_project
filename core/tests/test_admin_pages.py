import io
import shutil
import tempfile
from datetime import date, time, timedelta
from decimal import Decimal
from html.parser import HTMLParser

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from ninja.errors import HttpError
from PIL import Image

from core.admin import schedule_summary
from core.models import (
    Booking,
    Branch,
    Business,
    BusinessGallery,
    BusinessView,
    Category,
    Product,
    Service,
    User,
)
from core.utils.validators import validate_image


def png_file(name="photo.png", color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


CONTENT_TYPES = {
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def image_file(name, image_format, size=(8, 8), **save_options):
    """A real image of `image_format`, whatever `name` says."""
    buffer = io.BytesIO()
    Image.new("RGB", size, "orange").save(buffer, format=image_format, **save_options)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=CONTENT_TYPES[image_format])


def gif_file():
    return image_file("banner.gif", "GIF")


def large_png_file():
    # Stored uncompressed: about 5.6 MB, over the 5 MB limit
    return image_file("large.png", "PNG", size=(1400, 1400), compress_level=0)


def html_as_png_file():
    return SimpleUploadedFile(
        "photo.png", b"<html><script>alert(1)</script></html>", content_type="image/png",
    )


def api_image_error(file):
    """What the API (validate_image) answers for this upload."""
    try:
        validate_image(file)
    except HttpError as exc:
        return exc.message
    raise AssertionError(f"{file.name} passes validate_image")


class FormScraper(HTMLParser):
    """
    Collects what a browser would submit for one <form id=...> of a page, so
    tests can post admin forms with all their inlines without listing every
    management field by hand.
    """

    SKIPPED_INPUTS = {"file", "submit", "button", "image", "reset"}

    def __init__(self, form_id):
        super().__init__(convert_charrefs=True)
        self.form_id = form_id
        self.in_form = False
        self.data = {}
        self.select = None
        self.textarea = None

    def add(self, name, value):
        # The inline "add another" template is not a real row
        if name and "__prefix__" not in name:
            self.data.setdefault(name, []).append(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.in_form = attrs.get("id") == self.form_id
            return
        if not self.in_form or "disabled" in attrs:
            return

        if tag == "input":
            kind = (attrs.get("type") or "text").lower()
            if kind in self.SKIPPED_INPUTS:
                return
            if kind in ("checkbox", "radio") and "checked" not in attrs:
                return
            default = "on" if kind in ("checkbox", "radio") else ""
            self.add(attrs.get("name"), attrs.get("value", default))
        elif tag == "select":
            self.select = {
                "name": attrs.get("name"),
                "multiple": "multiple" in attrs,
                "first": None,
                "selected": [],
            }
        elif tag == "option" and self.select is not None:
            value = attrs.get("value", "")
            if self.select["first"] is None:
                self.select["first"] = value
            if "selected" in attrs:
                self.select["selected"].append(value)
        elif tag == "textarea":
            self.textarea = {"name": attrs.get("name"), "text": ""}

    def handle_data(self, data):
        if self.textarea is not None:
            self.textarea["text"] += data

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False
        elif tag == "select" and self.select is not None:
            values = self.select["selected"]
            # A single select without a selected option submits its first one
            if not values and not self.select["multiple"] and self.select["first"] is not None:
                values = [self.select["first"]]
            for value in values:
                self.add(self.select["name"], value)
            self.select = None
        elif tag == "textarea" and self.textarea is not None:
            text = self.textarea["text"]
            # Browsers drop the newline Django puts right after <textarea>
            if text.startswith("\r\n"):
                text = text[2:]
            elif text.startswith("\n"):
                text = text[1:]
            self.add(self.textarea["name"], text)
            self.textarea = None


class AdminPagesTests(TestCase):

    @classmethod
    def setUpClass(cls):
        # Uploaded images go to a throwaway MEDIA_ROOT, never to media/
        cls.media_root = tempfile.mkdtemp(prefix="bron-admin-tests-")
        cls.addClassCleanup(shutil.rmtree, cls.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=cls.media_root)
        media.enable()
        cls.addClassCleanup(media.disable)
        super().setUpClass()

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="admin",
            email="admin@bron.test",
            phone="+998900000001",
            password="AdminPass123!",
        )
        cls.owner = User.objects.create_user(
            username="owner",
            email="owner@bron.test",
            phone="+998900000002",
            password="OwnerPass123!",
            role="business_owner",
        )
        cls.customer = User.objects.create_user(
            username="customer",
            email="customer@bron.test",
            phone="+998900000003",
            password="CustomerPass123!",
            notify_promotions=True,
        )

        cls.category = Category.objects.get(slug="gym")
        cls.business = Business.objects.create(
            owner=cls.owner,
            name="Iron Gym",
            category=cls.category,
            address="Tashkent",
            phone="+998900000010",
            is_active=True,
        )
        cls.branch = Branch.objects.create(
            business=cls.business,
            name="Main",
            address="Tashkent",
            phone="+998900000011",
        )

        cls.tomorrow = timezone.localdate() + timedelta(days=1)
        cls.service = Service.objects.create(
            business=cls.business,
            title="Personal training",
            description="One hour with a coach",
            category="fitness",
            duration=30,
            capacity=3,
            price=Decimal("95000.00"),
            availability=[{"date": cls.tomorrow.isoformat(), "times": ["10:00", "23:00"]}],
        )

        cls.product = Product.objects.create(
            business=cls.business,
            name="Protein shake",
            price=Decimal("15000.50"),
            image=png_file("shake.png"),
        )
        cls.product_without_image = Product.objects.create(
            business=cls.business,
            name="Towel",
            price=Decimal("5000.00"),
        )

        cls.photo_a = BusinessGallery.objects.create(
            business=cls.business, image=png_file("a.png", "blue"), sort_order=0,
        )
        cls.photo_b = BusinessGallery.objects.create(
            business=cls.business, image=png_file("b.png", "green"), sort_order=1,
        )

        cls.booking = Booking.objects.create(
            user=cls.customer,
            business=cls.business,
            service=cls.service,
            branch=cls.branch,
            booking_date=cls.tomorrow,
            start_time=time(10, 0),
            end_time=time(10, 30),
            total_price=Decimal("205000.50"),
            items=[
                {"id": cls.service.id, "name": "Personal training", "price": "95000.00",
                 "quantity": 2, "kind": "service"},
                {"id": cls.product.id, "name": "Protein shake", "price": "15000.50",
                 "quantity": 1, "kind": "product"},
            ],
        )
        cls.booking.products.add(cls.product)

        cls.view = BusinessView.objects.create(
            business=cls.business, user=cls.customer, ip="127.0.0.1",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def scrape(self, url, form_id):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        parser = FormScraper(form_id)
        parser.feed(response.content.decode())
        self.assertTrue(parser.data, f"form #{form_id} not found on {url}")
        return parser.data

    @staticmethod
    def inline_row(data, prefix, obj=None):
        """Index of the inline row showing `obj`, or of the extra (new) row."""
        wanted = [str(obj.id) if obj is not None else ""]
        return next(
            key.split("-")[1] for key, value in data.items()
            if key.startswith(f"{prefix}-") and key.endswith("-id") and value == wanted
        )

    @staticmethod
    def inline_errors(response, prefix):
        """Per-row errors of one inline formset on a re-rendered admin page."""
        return next(
            inline.formset.errors for inline in response.context["inline_admin_formsets"]
            if inline.formset.prefix == prefix
        )

    # --- Pages render ---

    def test_changelist_add_and_change_pages_render(self):
        pages = [
            ("product", self.product.id),
            ("service", self.service.id),
            ("booking", self.booking.id),
            ("user", self.customer.id),
            ("businessgallery", self.photo_a.id),
            ("business", self.business.id),
            ("category", self.category.id),
        ]
        for model, pk in pages:
            for url in (
                f"/admin/core/{model}/",
                f"/admin/core/{model}/add/",
                f"/admin/core/{model}/{pk}/change/",
            ):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_business_view_log_is_read_only(self):
        changelist = self.client.get("/admin/core/businessview/")
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, "Iron Gym")

        # Rows come only from POST /api/businesses/{id}/view
        self.assertEqual(self.client.get("/admin/core/businessview/add/").status_code, 403)

        change = self.client.get(f"/admin/core/businessview/{self.view.id}/change/")
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, "127.0.0.1")
        self.assertNotContains(change, 'name="ip"')
        self.assertNotContains(change, 'name="business"')

    def test_other_category_is_listed(self):
        response = self.client.get("/admin/core/category/")
        self.assertContains(response, "Other")
        self.assertContains(response, "other")

    # --- Products ---

    def test_product_list_shows_thumbnails(self):
        response = self.client.get("/admin/core/product/")
        self.assertContains(response, f'src="{self.product.image.url}"')
        self.assertContains(response, "width:48px;height:48px")

    def test_product_change_page_keeps_upload_and_shows_preview(self):
        response = self.client.get(f"/admin/core/product/{self.product.id}/change/")
        self.assertContains(response, 'name="image"')
        self.assertContains(response, f'<img src="{self.product.image.url}"', html=False)

    # --- Image rules shared with the API (validate_image) ---

    def test_product_admin_rejects_images_the_api_rejects(self):
        url = f"/admin/core/product/{self.product.id}/change/"
        stored = self.product.image.name
        cases = {
            "gif": gif_file,
            "over 5 MB": large_png_file,
            # Not an image at all: Django's own image check already refuses it
            "html sent as png": html_as_png_file,
        }
        for label, make_file in cases.items():
            with self.subTest(label):
                data = self.scrape(url, "product_form")
                data["image"] = make_file()

                response = self.client.post(url, data)

                self.assertEqual(response.status_code, 200)
                errors = response.context["adminform"].form.errors.get("image")
                self.assertTrue(errors)
                if label != "html sent as png":
                    self.assertEqual(errors, [api_image_error(make_file())])
                self.product.refresh_from_db()
                self.assertEqual(self.product.image.name, stored)

    def test_product_admin_accepts_jpeg_png_and_webp(self):
        url = f"/admin/core/product/{self.product.id}/change/"
        # PNG bytes named .jpg are stored as .png, as with API uploads
        cases = [("photo.jpeg", "JPEG", ".jpg"), ("photo.webp", "WEBP", ".webp"), ("photo.jpg", "PNG", ".png")]
        for name, image_format, extension in cases:
            with self.subTest(name=name, image_format=image_format):
                data = self.scrape(url, "product_form")
                data["image"] = image_file(name, image_format)

                self.assertEqual(self.client.post(url, data).status_code, 302)

                self.product.refresh_from_db()
                self.assertTrue(self.product.image.name.endswith(extension), self.product.image.name)
                with Image.open(self.product.image.path) as stored:
                    self.assertEqual(stored.format, image_format)

    def test_editing_other_fields_does_not_recheck_stored_image(self):
        # Saved through the ORM, which applies no upload rules
        poster = Product.objects.create(
            business=self.business, name="Old poster", price=Decimal("1000.00"), image=gif_file(),
        )
        url = f"/admin/core/product/{poster.id}/change/"
        data = self.scrape(url, "product_form")
        data["name"] = "Poster"

        self.assertEqual(self.client.post(url, data).status_code, 302)
        stored = poster.image.name
        poster.refresh_from_db()
        self.assertEqual(poster.name, "Poster")
        self.assertEqual(poster.image.name, stored)

    def test_gallery_and_service_admin_reject_images_the_api_rejects(self):
        response = self.client.post("/admin/core/businessgallery/add/", {
            "business": self.business.id, "image": gif_file(), "sort_order": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["adminform"].form.errors.get("image"), [api_image_error(gif_file())],
        )
        self.assertEqual(self.business.gallery_images.count(), 2)

        url, data = self.service_form()
        data["image"] = gif_file()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["adminform"].form.errors.get("image"), [api_image_error(gif_file())],
        )
        self.service.refresh_from_db()
        self.assertFalse(self.service.image)

    def test_business_inlines_reject_images_the_api_rejects(self):
        def new_product(data):
            row = self.inline_row(data, "products")
            data.update({f"products-{row}-name": "Cap", f"products-{row}-price": "100"})
            return row

        cases = {
            "products": new_product,
            "gallery_images": lambda data: self.inline_row(data, "gallery_images"),
            "services": lambda data: self.inline_row(data, "services", self.service),
        }
        for prefix, pick_row in cases.items():
            with self.subTest(prefix):
                url, data = self.business_form()
                row = pick_row(data)
                data[f"{prefix}-{row}-image"] = gif_file()

                response = self.client.post(url, data)

                self.assertEqual(response.status_code, 200)
                errors = self.inline_errors(response, prefix)[int(row)]
                self.assertEqual(errors.get("image"), [api_image_error(gif_file())])
                self.assertEqual(self.business.products.count(), 2)
                self.assertEqual(self.business.gallery_images.count(), 2)
                self.service.refresh_from_db()
                self.assertFalse(self.service.image)

    def test_business_page_shows_inline_previews(self):
        response = self.client.get(f"/admin/core/business/{self.business.id}/change/")
        self.assertContains(response, f'src="{self.product.image.url}"')
        self.assertContains(response, f'src="{self.photo_a.image.url}"')
        self.assertContains(response, 'name="gallery_images-0-sort_order"')
        # The services inline hides the JSON schedule but summarizes it
        self.assertNotContains(response, 'name="services-0-availability"')
        self.assertContains(response, f"1 date, next {self.tomorrow.isoformat()}")
        self.assertContains(response, f"/admin/core/service/{self.service.id}/change/")

    # --- Services ---

    def test_service_list_shows_capacity_and_schedule(self):
        Service.objects.create(
            business=self.business, title="Open gym", description="-",
            category="fitness", duration=60, price=Decimal("30000.00"),
        )
        response = self.client.get("/admin/core/service/")
        self.assertContains(response, "Working hours")
        self.assertContains(response, f"1 date, next {self.tomorrow.isoformat()}")
        self.assertContains(response, 'class="field-capacity">3<')

    def test_service_add_page_explains_schedule_format(self):
        response = self.client.get("/admin/core/service/add/")
        self.assertContains(response, 'name="availability"')
        self.assertContains(response, "YYYY-MM-DD")
        self.assertContains(response, "HH:MM")
        self.assertContains(response, "working hours")

    def service_form(self, **changes):
        url = f"/admin/core/service/{self.service.id}/change/"
        data = self.scrape(url, "service_form")
        data.update(changes)
        return url, data

    def test_service_form_round_trips_unchanged(self):
        url, data = self.service_form()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.service.refresh_from_db()
        self.assertEqual(
            self.service.availability,
            [{"date": self.tomorrow.isoformat(), "times": ["10:00", "23:00"]}],
        )

    def test_service_form_saves_availability_normalized(self):
        url, data = self.service_form(availability=(
            '[{"date": "2030-01-02", "times": ["15:00", "09:00", "09:00"]},'
            ' {"date": "2030-01-01", "times": ["10:00:00"]}]'
        ))
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.service.refresh_from_db()
        self.assertEqual(self.service.availability, [
            {"date": "2030-01-01", "times": ["10:00"]},
            {"date": "2030-01-02", "times": ["09:00", "15:00"]},
        ])

    def test_service_form_empty_availability_means_working_hours(self):
        url, data = self.service_form(availability="")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.service.refresh_from_db()
        self.assertEqual(self.service.availability, [])

    def test_service_form_rejects_invalid_availability(self):
        cases = {
            "not json": "[{",
            "bad time": '[{"date": "2030-01-01", "times": ["25:00"]}]',
            "bad date": '[{"date": "01.01.2030", "times": ["10:00"]}]',
            "duplicate date": '[{"date": "2030-01-01", "times": []}, {"date": "2030-01-01", "times": []}]',
            "past midnight": '[{"date": "2030-01-01", "times": ["23:45"]}]',
            "not a list": '{"date": "2030-01-01"}',
        }
        for label, value in cases.items():
            with self.subTest(label):
                url, data = self.service_form(availability=value)
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors.get("availability"))
                self.service.refresh_from_db()
                self.assertEqual(
                    self.service.availability,
                    [{"date": self.tomorrow.isoformat(), "times": ["10:00", "23:00"]}],
                )

    def test_service_form_checks_schedule_against_new_duration(self):
        # 23:00 + 90 minutes would end after 23:59
        url, data = self.service_form(duration="90")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "would end after 23:59",
            str(response.context["adminform"].form.errors["availability"]),
        )
        self.service.refresh_from_db()
        self.assertEqual(self.service.duration, 30)

    def test_service_form_rejects_zero_duration(self):
        # The form field allows 0 (PositiveIntegerField); Service.clean() does not
        url, data = self.service_form(duration="0")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors.get("duration"))
        self.service.refresh_from_db()
        self.assertEqual(self.service.duration, 30)

    # --- Business page with all inlines ---

    def business_form(self):
        url = f"/admin/core/business/{self.business.id}/change/"
        return url, self.scrape(url, "business_form")

    def test_business_form_round_trips_unchanged(self):
        url, data = self.business_form()
        # The untouched extra gallery row posts an empty order and no file
        extra = self.inline_row(data, "gallery_images")
        self.assertEqual(data[f"gallery_images-{extra}-sort_order"], [""])

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        self.service.refresh_from_db()
        self.assertEqual(
            self.service.availability,
            [{"date": self.tomorrow.isoformat(), "times": ["10:00", "23:00"]}],
        )
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", "sort_order")),
            [(self.photo_a.id, 0), (self.photo_b.id, 1)],
        )

    def test_services_inline_reports_schedule_error_instead_of_crashing(self):
        url, data = self.business_form()
        index = self.inline_row(data, "services", self.service)
        data[f"services-{index}-duration"] = "90"

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Availability: Slot at 23:00")
        self.service.refresh_from_db()
        self.assertEqual(self.service.duration, 30)

    def test_services_inline_rejects_zero_duration(self):
        url, data = self.business_form()
        index = self.inline_row(data, "services", self.service)
        data[f"services-{index}-duration"] = "0"

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.inline_errors(response, "services")[int(index)].get("duration"))
        self.service.refresh_from_db()
        self.assertEqual(self.service.duration, 30)

    def test_gallery_inline_updates_sort_order(self):
        url, data = self.business_form()
        for key, value in list(data.items()):
            # The extra (empty) row has id=""
            if key.startswith("gallery_images-") and key.endswith("-id") and value[0]:
                index = key.split("-")[1]
                photo_id = int(value[0])
                data[f"gallery_images-{index}-sort_order"] = "0" if photo_id == self.photo_b.id else "5"

        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", flat=True)),
            [self.photo_b.id, self.photo_a.id],
        )

    def test_gallery_inline_appends_new_pictures_in_order(self):
        url, data = self.business_form()
        first = self.inline_row(data, "gallery_images")
        second = str(int(first) + 1)
        # A second new row, as "Add another" would create it
        for key, value in list(data.items()):
            if key.startswith(f"gallery_images-{first}-"):
                data[key.replace(f"-{first}-", f"-{second}-", 1)] = value
        data["gallery_images-TOTAL_FORMS"] = [str(int(second) + 1)]
        data[f"gallery_images-{first}-image"] = png_file("c.png", "white")
        data[f"gallery_images-{second}-image"] = png_file("d.png", "black")

        self.assertEqual(self.client.post(url, data).status_code, 302)

        new = list(
            self.business.gallery_images.exclude(pk__in=[self.photo_a.pk, self.photo_b.pk]).order_by("id")
        )
        self.assertEqual([photo.sort_order for photo in new], [2, 3])
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", flat=True)),
            [self.photo_a.id, self.photo_b.id, new[0].id, new[1].id],
        )

    def test_gallery_inline_empty_order_moves_picture_to_end(self):
        url, data = self.business_form()
        data[f"gallery_images-{self.inline_row(data, 'gallery_images', self.photo_a)}-sort_order"] = ""

        self.assertEqual(self.client.post(url, data).status_code, 302)

        self.photo_a.refresh_from_db()
        self.assertEqual(self.photo_a.sort_order, 2)
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", flat=True)),
            [self.photo_b.id, self.photo_a.id],
        )

    # --- Bookings ---

    def test_booking_change_page_renders_items_table(self):
        # A stored total unlike the lines' sum, so 205000.50 can come only from the table
        Booking.objects.filter(pk=self.booking.pk).update(total_price=Decimal("1.00"))

        response = self.client.get(f"/admin/core/booking/{self.booking.id}/change/")

        self.assertContains(response, "booking-items")
        self.assertContains(response, "Protein shake")
        self.assertContains(response, "Unit price")
        self.assertContains(response, '<td style="text-align:right">95000.00</td>', html=True)
        self.assertContains(response, '<td style="text-align:right">190000.00</td>', html=True)
        self.assertContains(
            response,
            '<tfoot><tr><th colspan="4" style="text-align:right">Total</th>'
            '<th style="text-align:right">205000.50</th></tr></tfoot>',
            html=True,
        )
        # Snapshot only, not an editable field
        self.assertNotContains(response, 'name="items"')

    def test_booking_change_page_locks_snapshot_lines(self):
        url = f"/admin/core/booking/{self.booking.id}/change/"
        response = self.client.get(url)
        for field in ("service", "products", "total_price"):
            self.assertNotContains(response, f'name="{field}"')
        for field in ("status", "staff", "booking_date", "notes"):
            self.assertContains(response, f'name="{field}"')

        other_service = Service.objects.create(
            business=self.business, title="Sauna", description="-",
            category="fitness", duration=60, price=Decimal("1.00"),
        )
        data = self.scrape(url, "booking_form")
        # Values a crafted request could still send are ignored
        data.update({
            "status": "confirmed",
            "service": str(other_service.id),
            "products": [str(self.product_without_image.id)],
            "total_price": "1.00",
        })

        self.assertEqual(self.client.post(url, data).status_code, 302)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "confirmed")
        self.assertEqual(self.booking.service, self.service)
        self.assertEqual(list(self.booking.products.all()), [self.product])
        self.assertEqual(self.booking.total_price, Decimal("205000.50"))
        self.assertEqual(len(self.booking.items), 2)

    def booking_add_form(self, products):
        url = "/admin/core/booking/add/"
        data = self.scrape(url, "booking_form")
        data.update({
            "user": str(self.customer.id),
            "business": str(self.business.id),
            "service": str(self.service.id),
            "branch": str(self.branch.id),
            "booking_date": self.tomorrow.isoformat(),
            "start_time": "10:00",
            "end_time": "10:30",
            "products": [str(product.id) for product in products],
        })
        return url, data

    def test_booking_add_builds_items_snapshot(self):
        response = self.client.get("/admin/core/booking/add/")
        self.assertContains(response, 'name="service"')
        self.assertContains(response, 'name="products"')
        self.assertNotContains(response, 'name="total_price"')
        self.assertContains(response, "calculated when the booking is created")

        # The snapshot takes the prices at the moment of saving
        Product.objects.filter(pk=self.product.pk).update(price=Decimal("16000"))
        url, data = self.booking_add_form([self.product_without_image, self.product])
        data["total_price"] = "1.00"

        self.assertEqual(self.client.post(url, data).status_code, 302)

        booking = Booking.objects.exclude(pk=self.booking.pk).get()
        self.assertEqual(booking.items, [
            {"id": self.service.id, "name": "Personal training", "price": "95000.00",
             "quantity": 1, "kind": "service"},
            {"id": self.product.id, "name": "Protein shake", "price": "16000.00",
             "quantity": 1, "kind": "product"},
            {"id": self.product_without_image.id, "name": "Towel", "price": "5000.00",
             "quantity": 1, "kind": "product"},
        ])
        self.assertEqual(booking.total_price, Decimal("116000.00"))
        self.assertEqual(
            set(booking.products.values_list("id", flat=True)),
            {self.product.id, self.product_without_image.id},
        )

    def test_booking_add_without_products_charges_the_service(self):
        url, data = self.booking_add_form([])

        self.assertEqual(self.client.post(url, data).status_code, 302)

        booking = Booking.objects.exclude(pk=self.booking.pk).get()
        self.assertEqual(booking.items, [
            {"id": self.service.id, "name": "Personal training", "price": "95000.00",
             "quantity": 1, "kind": "service"},
        ])
        self.assertEqual(booking.total_price, Decimal("95000.00"))

    def test_booking_add_rejects_total_over_column_limit(self):
        # Booking.total_price holds at most 99999999.99
        expensive = Product.objects.create(
            business=self.business, name="Treadmill", price=Decimal("99999999.99"),
        )
        url, data = self.booking_add_form([expensive])

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Order total is too large",
            response.context["adminform"].form.non_field_errors(),
        )
        self.assertEqual(Booking.objects.count(), 1)

    def test_booking_list_shows_items_count(self):
        response = self.client.get("/admin/core/booking/")
        self.assertContains(response, 'class="field-items_count">2<')

    def test_booking_form_save_keeps_items(self):
        url = f"/admin/core/booking/{self.booking.id}/change/"
        data = self.scrape(url, "booking_form")
        data["notes"] = "Window seat"

        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.notes, "Window seat")
        self.assertEqual(len(self.booking.items), 2)
        self.assertEqual(self.booking.items[0]["price"], "95000.00")

    def test_booking_items_table_tolerates_malformed_rows(self):
        Booking.objects.filter(pk=self.booking.pk).update(items=[
            {"name": "Mystery", "price": "abc", "quantity": "x"},
            "garbage",
        ])
        response = self.client.get(f"/admin/core/booking/{self.booking.id}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mystery")

    # --- Users ---

    def test_user_change_page_has_notification_settings(self):
        response = self.client.get(f"/admin/core/user/{self.customer.id}/change/")
        self.assertContains(response, "Notifications")
        for field in ("notify_push", "notify_email", "notify_booking_reminder", "notify_promotions"):
            self.assertContains(response, f'name="{field}"')

    def test_user_form_saves_notification_settings(self):
        url = f"/admin/core/user/{self.customer.id}/change/"
        data = self.scrape(url, "user_form")
        data.pop("notify_promotions", None)
        data.pop("notify_email", None)

        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.notify_promotions)
        self.assertFalse(self.customer.notify_email)
        self.assertTrue(self.customer.notify_push)
        # Password handling is untouched by the form
        self.assertTrue(self.customer.check_password("CustomerPass123!"))

    def test_user_list_filters_by_promotions(self):
        response = self.client.get("/admin/core/user/?notify_promotions__exact=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "customer@bron.test")
        self.assertNotContains(response, "owner@bron.test")

    # --- Business gallery ---

    def test_gallery_list_shows_thumbnail_and_editable_order(self):
        response = self.client.get("/admin/core/businessgallery/")
        self.assertContains(response, f'src="{self.photo_a.image.url}"')
        self.assertContains(response, 'name="form-0-sort_order"')

    def test_gallery_list_editable_sort_order(self):
        data = self.scrape("/admin/core/businessgallery/", "changelist-form")
        for key, value in list(data.items()):
            if key.startswith("form-") and key.endswith("-id"):
                index = key.split("-")[1]
                data[f"form-{index}-sort_order"] = "7" if value == [str(self.photo_a.id)] else "2"
        data["_save"] = "Save"

        response = self.client.post("/admin/core/businessgallery/", data)

        self.assertEqual(response.status_code, 302)
        self.photo_a.refresh_from_db()
        self.photo_b.refresh_from_db()
        self.assertEqual(self.photo_a.sort_order, 7)
        self.assertEqual(self.photo_b.sort_order, 2)
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", flat=True)),
            [self.photo_b.id, self.photo_a.id],
        )

    def test_gallery_add_page_leaves_sort_order_empty(self):
        url = "/admin/core/businessgallery/add/"
        self.assertContains(self.client.get(url), "Leave empty to put the picture at the end")
        self.assertEqual(self.scrape(url, "businessgallery_form")["sort_order"], [""])

    def test_gallery_add_puts_picture_at_the_end(self):
        url = "/admin/core/businessgallery/add/"
        response = self.client.post(url, {
            "business": self.business.id, "image": png_file("c.png", "white"), "sort_order": "",
        })
        self.assertEqual(response.status_code, 302)

        photo = self.business.gallery_images.latest("id")
        self.assertEqual(photo.sort_order, 2)
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", flat=True)),
            [self.photo_a.id, self.photo_b.id, photo.id],
        )

        # First picture of a business starts at 0, like an API upload
        other = Business.objects.create(
            owner=self.owner, name="Yoga Club", category=self.category,
            address="Tashkent", phone="+998900000020",
        )
        response = self.client.post(url, {
            "business": other.id, "image": png_file("y.png"), "sort_order": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(other.gallery_images.get().sort_order, 0)

    def test_gallery_add_keeps_explicit_order(self):
        response = self.client.post("/admin/core/businessgallery/add/", {
            "business": self.business.id, "image": png_file("c.png", "white"), "sort_order": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.business.gallery_images.latest("id").sort_order, 0)

    def test_gallery_add_at_the_end_is_capped_like_the_api(self):
        from core.services.business_gallery import MAX_SORT_ORDER

        url = "/admin/core/businessgallery/add/"
        # A PUT may already have moved a picture to the largest position
        BusinessGallery.objects.filter(pk=self.photo_b.pk).update(sort_order=MAX_SORT_ORDER)

        response = self.client.post(url, {
            "business": self.business.id, "image": png_file("c.png", "white"), "sort_order": "",
        })
        self.assertEqual(response.status_code, 302)
        photo = self.business.gallery_images.latest("id")
        # Not MAX + 1, which overflows the PostgreSQL integer column; the tie goes by id
        self.assertEqual(photo.sort_order, MAX_SORT_ORDER)
        self.assertEqual(
            list(self.business.gallery_images.values_list("id", flat=True)),
            [self.photo_a.id, self.photo_b.id, photo.id],
        )

        # An explicit value above the column range is a form error, not a database error
        response = self.client.post(url, {
            "business": self.business.id, "image": png_file("d.png"), "sort_order": str(MAX_SORT_ORDER + 1),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("sort_order", response.context["adminform"].form.errors)
        self.assertEqual(self.business.gallery_images.count(), 3)


class ScheduleSummaryTests(TestCase):

    def test_summaries(self):
        today = timezone.localdate()
        past = (today - timedelta(days=3)).isoformat()
        soon = (today + timedelta(days=2)).isoformat()
        later = (today + timedelta(days=9)).isoformat()

        self.assertEqual(schedule_summary([]), "Working hours")
        self.assertEqual(schedule_summary(None), "Working hours")
        self.assertEqual(
            schedule_summary([
                {"date": past, "times": ["10:00"]},
                {"date": later, "times": ["10:00"]},
                {"date": soon, "times": ["09:00"]},
            ]),
            f"3 dates, next {soon}",
        )
        self.assertEqual(
            schedule_summary([{"date": today.isoformat(), "times": ["10:00"]}]),
            f"1 date, next {today.isoformat()}",
        )
        older = (today - timedelta(days=10)).isoformat()
        self.assertEqual(
            schedule_summary([{"date": past, "times": ["10:00"]}, {"date": older, "times": []}]),
            "2 dates (all past)",
        )
        # Only days off ahead: nothing bookable, but not "all past" either
        self.assertEqual(
            schedule_summary([{"date": soon, "times": []}]),
            "1 date, no upcoming times",
        )
