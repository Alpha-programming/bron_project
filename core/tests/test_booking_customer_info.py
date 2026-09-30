from datetime import time, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import Booking, Branch, Business, Category, Service, Staff, User
from core.utils.jwt import create_access_token

USER_KEYS = {"first_name", "last_name", "full_name", "username", "avatar"}


def make_user(name, n, **extra):
    return User.objects.create_user(
        username=name,
        email=f"{name}@bron.test",
        phone=f"+99892000{n:04d}",
        password="Pass12345!",
        **extra,
    )


class BookingCustomerInfoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner", 1, role="business_owner")
        cls.full = make_user("full", 2, first_name="Имя", last_name="Фамилия")
        cls.first_only = make_user("first_only", 3, first_name="Ali")
        cls.nameless = make_user("nameless", 4)
        # Stored path only; the URL is built without touching the file
        cls.full.avatar = "avatars/full.png"
        cls.full.save(update_fields=["avatar"])

        cls.business = Business.objects.create(
            owner=cls.owner,
            name="Iron Gym",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998710000001",
            is_active=True,
        )
        cls.branch = Branch.objects.create(business=cls.business, name="Main", address="A", phone="1")
        cls.staff = Staff.objects.create(business=cls.business, full_name="Coach", position="Coach")
        cls.service = Service.objects.create(
            business=cls.business,
            title="Training",
            description="",
            category="gym",
            duration=60,
            price=Decimal("95000.00"),
        )
        day = timezone.localdate() + timedelta(days=1)

        cls.bookings = {}
        for hour, customer in ((9, cls.full), (11, cls.first_only), (13, cls.nameless)):
            cls.bookings[customer.username] = Booking.objects.create(
                user=customer,
                business=cls.business,
                service=cls.service,
                branch=cls.branch,
                staff=cls.staff,
                booking_date=day,
                start_time=time(hour),
                end_time=time(hour + 1),
            )

    def get(self, url, user):
        return self.client.get(
            url,
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}",
        )

    def test_business_bookings_include_customer(self):
        response = self.get(f"/api/bookings/business/{self.business.id}", self.owner)

        self.assertEqual(response.status_code, 200, response.content)
        rows = {row["user_id"]: row["user"] for row in response.json()}
        self.assertEqual(len(rows), 3)

        for user in rows.values():
            # Only display data: no phone, email or other personal fields
            self.assertEqual(set(user), USER_KEYS)

        self.assertEqual(rows[self.full.id], {
            "first_name": "Имя",
            "last_name": "Фамилия",
            "full_name": "Имя Фамилия",
            "username": "full",
            "avatar": "https://testserver/media/avatars/full.png",
        })
        self.assertEqual(rows[self.first_only.id]["full_name"], "Ali")
        self.assertEqual(rows[self.nameless.id]["full_name"], "")
        self.assertEqual(rows[self.nameless.id]["username"], "nameless")
        self.assertIsNone(rows[self.nameless.id]["avatar"])

    def test_booking_detail_includes_customer_for_owner_and_customer(self):
        booking = self.bookings["full"]

        for viewer in (self.owner, self.full):
            with self.subTest(viewer=viewer.username):
                response = self.get(f"/api/bookings/{booking.id}", viewer)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["user_id"], self.full.id)
                self.assertEqual(response.json()["user"]["full_name"], "Имя Фамилия")

    def test_staff_bookings_include_customer(self):
        response = self.get(f"/api/bookings/staff/{self.staff.id}", self.owner)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(all(set(row["user"]) == USER_KEYS for row in response.json()))

    def test_no_extra_query_per_booking(self):
        url = f"/api/bookings/business/{self.business.id}"
        self.get(url, self.owner)

        with CaptureQueriesContext(connection) as three:
            self.get(url, self.owner)

        Booking.objects.filter(user=self.nameless).delete()
        Booking.objects.filter(user=self.first_only).delete()

        with CaptureQueriesContext(connection) as one:
            self.get(url, self.owner)

        self.assertEqual(len(three), len(one))

    def test_openapi_documents_customer(self):
        spec = self.client.get("/api/openapi.json", secure=True).json()
        schemas = spec["components"]["schemas"]

        user = schemas["BookingUserSchema"]["properties"]
        self.assertEqual(set(user), USER_KEYS)
        self.assertIn({"type": "null"}, user["avatar"]["anyOf"])

        out = schemas["BookingOutSchema"]["properties"]
        self.assertIn("user", out)
        self.assertIn("user", schemas["BookingOutSchema"]["required"])
