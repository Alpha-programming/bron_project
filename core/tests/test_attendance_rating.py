from datetime import time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from core.models import Booking, Branch, Business, Category, Review, Service, User
from core.utils.jwt import create_access_token


def make_user(name, n, role="customer"):
    return User.objects.create_user(
        username=name,
        email=f"{name}@bron.test",
        phone=f"+99891000{n:04d}",
        password="Pass12345!",
        role=role,
    )


class AttendanceRatingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner", 1, role="business_owner")
        cls.stranger = make_user("stranger", 2, role="business_owner")
        cls.customer = make_user("customer", 3)

        cls.business = Business.objects.create(
            owner=cls.owner,
            name="Iron Gym",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998710000001",
            is_active=True,
        )
        cls.branch = Branch.objects.create(business=cls.business, name="Main", address="A", phone="1")
        cls.service = Service.objects.create(
            business=cls.business,
            title="Training",
            description="",
            category="gym",
            duration=60,
            price=Decimal("95000.00"),
        )
        cls.day = timezone.localdate() + timedelta(days=1)

    def booking(self, status="confirmed", hour=10, user=None):
        return Booking.objects.create(
            user=user or self.customer,
            business=self.business,
            service=self.service,
            branch=self.branch,
            booking_date=self.day,
            start_time=time(hour),
            end_time=time(hour + 1),
            status=status,
        )

    def auth(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}

    def mark(self, booking, status, user=None, **extra):
        return self.client.patch(
            f"/api/bookings/{booking.id}/attendance",
            data={"status": status, **extra},
            content_type="application/json",
            secure=True,
            **self.auth(user or self.owner),
        )

    def rating(self, customer=None):
        response = self.client.get(
            f"/api/reviews/customer/{(customer or self.customer).id}/rating",
            secure=True,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    # --- PATCH /api/bookings/{id}/attendance ---

    def test_owner_marks_confirmed_booking(self):
        booking = self.booking()

        response = self.mark(booking, "visited")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["attendance_status"], "visited")
        self.assertEqual(response.json()["status"], "completed")
        booking.refresh_from_db()
        self.assertEqual(booking.attendance_status, "visited")
        self.assertIsNotNone(booking.attendance_updated_at)

    def test_response_returns_saved_mark_for_each_status(self):
        for hour, status in ((9, "visited"), (11, "late"), (13, "no_show")):
            with self.subTest(status=status):
                booking = self.booking(hour=hour)
                response = self.mark(booking, status)
                self.assertEqual(response.status_code, 200, response.content)
                booking.refresh_from_db()
                self.assertEqual(response.json()["attendance_status"], booking.attendance_status)
                self.assertEqual(booking.attendance_status, status)

    def test_invalid_status_is_422(self):
        booking = self.booking()

        response = self.mark(booking, "something_wrong")

        self.assertEqual(response.status_code, 422)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance_status, "not_set")

    def test_only_confirmed_bookings_can_be_marked(self):
        for status in ("pending", "cancelled", "rejected"):
            with self.subTest(status=status):
                booking = self.booking(status=status)
                response = self.mark(booking, "visited")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["detail"], "Booking must be confirmed first.")

    def test_only_owner_of_the_business_can_mark(self):
        booking = self.booking()

        self.assertEqual(self.mark(booking, "visited", user=self.stranger).status_code, 403)
        self.assertEqual(self.mark(booking, "visited", user=self.customer).status_code, 403)

        response = self.client.patch(
            f"/api/bookings/{booking.id}/attendance",
            data={"status": "visited"},
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_booking_is_404(self):
        response = self.client.patch(
            "/api/bookings/999999/attendance",
            data={"status": "visited"},
            content_type="application/json",
            secure=True,
            **self.auth(self.owner),
        )
        self.assertEqual(response.status_code, 404)

    def test_late_extra_wait_limits(self):
        booking = self.booking()

        self.assertEqual(self.mark(booking, "late", extra_wait_minutes=11).status_code, 400)
        self.assertEqual(self.mark(booking, "late", extra_wait_minutes=-1).status_code, 400)

        response = self.mark(booking, "late", extra_wait_minutes=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["extra_wait_minutes"], 10)

        # Other marks drop the waiting time
        response = self.mark(booking, "no_show", extra_wait_minutes=7)
        self.assertEqual(response.json()["extra_wait_minutes"], 0)

    def test_mark_can_be_changed_after_visited(self):
        booking = self.booking()
        self.mark(booking, "visited")

        response = self.mark(booking, "no_show")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["attendance_status"], "no_show")
        self.assertEqual(response.json()["status"], "confirmed")

        response = self.mark(booking, "visited")
        self.assertEqual(response.json()["status"], "completed")

    def test_repeating_same_mark_changes_nothing(self):
        booking = self.booking()
        self.mark(booking, "late", extra_wait_minutes=5)
        booking.refresh_from_db()
        marked_at = booking.attendance_updated_at

        with CaptureQueriesContext(connection) as queries:
            response = self.mark(booking, "late", extra_wait_minutes=5)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(q["sql"].startswith("UPDATE") for q in queries.captured_queries))
        booking.refresh_from_db()
        self.assertEqual(booking.attendance_updated_at, marked_at)

    def test_openapi_documents_status_values(self):
        spec = self.client.get("/api/openapi.json", secure=True).json()

        schema = spec["components"]["schemas"]["BookingAttendanceSchema"]["properties"]["status"]
        self.assertEqual(schema["enum"], ["visited", "late", "no_show"])

        operation = spec["paths"]["/api/bookings/{booking_id}/attendance"]["patch"]
        self.assertEqual(set(operation["responses"]), {"200", "400", "401", "403", "404"})

    # --- GET /api/reviews/customer/{id}/rating ---

    def test_rating_without_evaluated_bookings(self):
        self.booking()

        data = self.rating()

        self.assertIsNone(data["booking_rating"])
        self.assertEqual(data["evaluated_bookings_count"], 0)
        self.assertEqual((data["on_time_count"], data["late_count"], data["no_show_count"]), (0, 0, 0))

    def test_rating_counts_each_mark_with_its_points(self):
        self.mark(self.booking(hour=9), "visited")
        self.mark(self.booking(hour=11), "late")
        self.mark(self.booking(hour=13), "no_show")

        data = self.rating()

        # (5 + 3 + 2.5) / 3
        self.assertEqual(data["booking_rating"], 3.5)
        self.assertEqual(data["evaluated_bookings_count"], 3)
        self.assertEqual((data["on_time_count"], data["late_count"], data["no_show_count"]), (1, 1, 1))

    def test_rating_is_rounded_to_two_decimals(self):
        self.mark(self.booking(hour=9), "visited")
        self.mark(self.booking(hour=11), "visited")
        self.mark(self.booking(hour=13), "late")

        # 13 / 3 = 4.333...
        self.assertEqual(self.rating()["booking_rating"], 4.33)

    def test_repeated_mark_is_counted_once(self):
        booking = self.booking()
        for _ in range(3):
            self.mark(booking, "visited")

        data = self.rating()

        self.assertEqual(data["evaluated_bookings_count"], 1)
        self.assertEqual(data["on_time_count"], 1)
        self.assertEqual(data["booking_rating"], 5.0)

    def test_changed_mark_replaces_previous_result(self):
        booking = self.booking()
        self.mark(booking, "visited")
        self.mark(booking, "no_show")

        data = self.rating()

        self.assertEqual(data["evaluated_bookings_count"], 1)
        self.assertEqual((data["on_time_count"], data["no_show_count"]), (0, 1))
        self.assertEqual(data["booking_rating"], 2.5)

    def test_cancelled_booking_is_not_counted(self):
        kept = self.booking(hour=9)
        dropped = self.booking(hour=11)
        self.mark(kept, "visited")
        self.mark(dropped, "no_show")

        # A marked booking that is cancelled afterwards leaves the rating
        cancel = self.client.patch(
            f"/api/bookings/{dropped.id}/cancel", secure=True, **self.auth(self.owner)
        )
        self.assertEqual(cancel.status_code, 200, cancel.content)

        data = self.rating()

        self.assertEqual(data["evaluated_bookings_count"], 1)
        self.assertEqual(data["no_show_count"], 0)
        self.assertEqual(data["booking_rating"], 5.0)

    def test_only_this_customers_bookings_count(self):
        other = make_user("other_customer", 4)
        self.mark(self.booking(hour=9, user=other), "no_show")
        self.mark(self.booking(hour=11), "visited")

        self.assertEqual(self.rating()["booking_rating"], 5.0)
        self.assertEqual(self.rating(other)["booking_rating"], 2.5)

    def test_review_rating_stays_separate(self):
        booking = self.booking()
        self.mark(booking, "no_show")
        Review.objects.create(
            user=self.owner,
            customer=self.customer,
            booking=booking,
            review_type="customer",
            rating=4,
            comment="",
        )

        data = self.rating()

        self.assertEqual(data["rating"], 4.0)
        self.assertEqual(data["reviews_count"], 1)
        self.assertEqual(data["booking_rating"], 2.5)
        self.assertEqual(data["evaluated_bookings_count"], 1)

    def test_rating_for_unknown_customer_is_404(self):
        response = self.client.get("/api/reviews/customer/999999/rating", secure=True)
        self.assertEqual(response.status_code, 404)

    def test_openapi_documents_rating_fields(self):
        spec = self.client.get("/api/openapi.json", secure=True).json()

        props = spec["components"]["schemas"]["CustomerRatingSchema"]["properties"]
        for field in (
            "booking_rating",
            "evaluated_bookings_count",
            "on_time_count",
            "late_count",
            "no_show_count",
        ):
            self.assertIn(field, props)
            self.assertTrue(props[field]["description"])
        self.assertIn({"type": "null"}, props["booking_rating"]["anyOf"])
