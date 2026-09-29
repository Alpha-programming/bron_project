import json
import sys
from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import (
    BlockedDate,
    Booking,
    Branch,
    Business,
    Category,
    Service,
    WorkingHours,
)
from core.models import User
from core.services.service import _working_hours_slots, get_service_availability
from core.utils.jwt import create_access_token
from core.utils.schedule import normalize_availability, schedule_slots

FAR_FUTURE = date(9999, 12, 31)


def iso(day):
    return day.isoformat()


class TraceBudgetExceeded(Exception):
    pass


def call_with_trace_budget(func, *args, budget=10_000):
    """
    Runs func(*args) but aborts it after `budget` trace events, so an endless
    loop (e.g. a slot generator stepping by 0 minutes) fails the test
    instead of hanging the whole suite.
    """
    events = 0

    def tracer(frame, event, arg):
        nonlocal events
        events += 1
        if events > budget:
            raise TraceBudgetExceeded(f"{func.__name__} did not finish, endless loop?")
        return tracer

    previous = sys.gettrace()
    sys.settrace(tracer)
    try:
        return func(*args)
    finally:
        sys.settrace(previous)


class ServiceAvailabilityTestBase(TestCase):
    """
    Dates are relative to timezone.localdate() and start tomorrow, so the
    "already started today" rule never interferes with the assertions.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@bron.test",
            phone="+998900000101",
            password="OwnerPass123!",
            role="business_owner",
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@bron.test",
            phone="+998900000102",
            password="OtherPass123!",
        )
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@bron.test",
            phone="+998900000103",
            password="CustPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Gym",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998900000104",
            is_active=True,
        )
        self.branch = Branch.objects.create(
            business=self.business,
            name="Main",
            address="Tashkent",
            phone="+998900000105",
        )

        self.today = timezone.localdate()
        self.d1 = self.today + timedelta(days=1)
        self.d2 = self.today + timedelta(days=2)
        self.d3 = self.today + timedelta(days=3)
        self.d4 = self.today + timedelta(days=4)

    # --- helpers ---

    def auth(self, user=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user or self.owner)}"}

    def post_json(self, url, payload, user=None):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json",
            secure=True, **self.auth(user),
        )

    def put_json(self, url, payload, user=None):
        return self.client.put(
            url, data=json.dumps(payload), content_type="application/json",
            secure=True, **self.auth(user),
        )

    def get(self, url, params=None):
        return self.client.get(url, params or {}, secure=True)

    def make_service(self, availability=None, duration=60, capacity=1, **extra):
        return Service.objects.create(
            business=self.business,
            title=extra.pop("title", "Training"),
            description="Personal training",
            category="fitness",
            duration=duration,
            price="100000.00",
            capacity=capacity,
            availability=availability or [],
            **extra,
        )

    def set_working_hours(self, day, open_time, close_time, is_closed=False):
        WorkingHours.objects.create(
            business=self.business,
            day_of_week=day.weekday(),
            open_time=open_time,
            close_time=close_time,
            is_closed=is_closed,
        )

    def book(self, service, day, start, end, guests=1, status="confirmed"):
        return Booking.objects.create(
            user=self.customer,
            business=self.business,
            service=service,
            branch=self.branch,
            booking_date=day,
            start_time=start,
            end_time=end,
            guest_count=guests,
            status=status,
        )

    def create_payload(self, **overrides):
        payload = {
            "business_id": self.business.id,
            "title": "Yoga",
            "description": "Group yoga",
            "category": "fitness",
            "duration": 60,
            "price": "50000.00",
            "capacity": 5,
        }
        payload.update(overrides)
        return payload


class ServiceScheduleCrudTests(ServiceAvailabilityTestBase):

    def test_create_without_availability_defaults_to_empty(self):
        response = self.post_json("/api/services/create", self.create_payload())

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["availability"], [])
        self.assertEqual(Service.objects.get(id=response.json()["id"]).availability, [])

    def test_create_with_availability_is_normalized(self):
        payload = self.create_payload(availability=[
            {"date": iso(self.d2), "times": ["18:00", "09:00", "09:00:00"]},
            {"date": iso(self.d1), "times": ["14:30", "10:00"]},
            {"date": iso(self.d3), "times": []},
        ])

        response = self.post_json("/api/services/create", payload)

        self.assertEqual(response.status_code, 200, response.content)
        expected = [
            {"date": iso(self.d1), "times": ["10:00", "14:30"]},
            {"date": iso(self.d2), "times": ["09:00", "18:00"]},
            {"date": iso(self.d3), "times": []},
        ]
        self.assertEqual(response.json()["availability"], expected)
        # Stored as plain JSON strings, not date objects
        self.assertEqual(Service.objects.get(id=response.json()["id"]).availability, expected)

    def test_create_rejects_bad_date(self):
        for bad in ("2026-13-01", "01.10.2026", "tomorrow"):
            with self.subTest(date=bad):
                response = self.post_json("/api/services/create", self.create_payload(
                    availability=[{"date": bad, "times": ["10:00"]}]
                ))
                self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(Service.objects.exists())

    def test_create_rejects_bad_time(self):
        for bad in ("25:00", "9:00", "10:60", "10am"):
            with self.subTest(time=bad):
                response = self.post_json("/api/services/create", self.create_payload(
                    availability=[{"date": iso(self.d1), "times": [bad]}]
                ))
                self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(Service.objects.exists())

    def test_create_rejects_duplicate_date(self):
        response = self.post_json("/api/services/create", self.create_payload(availability=[
            {"date": iso(self.d1), "times": ["10:00"]},
            {"date": iso(self.d1), "times": ["12:00"]},
        ]))

        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn("more than once", response.content.decode())

    def test_create_rejects_slot_ending_after_midnight(self):
        response = self.post_json("/api/services/create", self.create_payload(
            duration=60,
            availability=[{"date": iso(self.d1), "times": ["22:00", "23:30"]}],
        ))

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("23:59", response.json()["detail"])
        self.assertFalse(Service.objects.exists())

    def test_create_slot_ending_exactly_at_2359_is_allowed(self):
        response = self.post_json("/api/services/create", self.create_payload(
            duration=59,
            availability=[{"date": iso(self.d1), "times": ["23:00"]}],
        ))

        self.assertEqual(response.status_code, 200, response.content)

    def test_create_for_foreign_business_is_forbidden(self):
        response = self.post_json(
            "/api/services/create",
            self.create_payload(availability=[{"date": iso(self.d1), "times": ["10:00"]}]),
            user=self.other,
        )

        self.assertEqual(response.status_code, 403)

    def test_update_replaces_schedule(self):
        service = self.make_service(availability=[
            {"date": iso(self.d1), "times": ["10:00"]},
            {"date": iso(self.d2), "times": ["11:00"]},
        ])

        response = self.put_json(f"/api/services/{service.id}", {
            "availability": [{"date": iso(self.d3), "times": ["16:00", "08:00"]}],
        })

        self.assertEqual(response.status_code, 200, response.content)
        expected = [{"date": iso(self.d3), "times": ["08:00", "16:00"]}]
        self.assertEqual(response.json()["availability"], expected)
        service.refresh_from_db()
        self.assertEqual(service.availability, expected)

    def test_update_clears_schedule_with_null_and_empty_list(self):
        for cleared in (None, []):
            with self.subTest(value=cleared):
                service = self.make_service(availability=[{"date": iso(self.d1), "times": ["10:00"]}])

                response = self.put_json(f"/api/services/{service.id}", {"availability": cleared})

                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["availability"], [])
                service.refresh_from_db()
                self.assertEqual(service.availability, [])

    def test_update_without_availability_keeps_schedule(self):
        schedule = [{"date": iso(self.d1), "times": ["10:00"]}]
        service = self.make_service(availability=schedule)

        response = self.put_json(f"/api/services/{service.id}", {"title": "Boxing", "price": "1.00"})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["availability"], schedule)
        service.refresh_from_db()
        self.assertEqual(service.title, "Boxing")
        self.assertEqual(service.availability, schedule)

    def test_update_rejects_bad_schedule(self):
        schedule = [{"date": iso(self.d1), "times": ["10:00"]}]
        service = self.make_service(availability=schedule)

        response = self.put_json(f"/api/services/{service.id}", {
            "availability": [{"date": iso(self.d1), "times": ["24:00"]}],
        })

        self.assertEqual(response.status_code, 422, response.content)
        service.refresh_from_db()
        self.assertEqual(service.availability, schedule)

    def test_update_checks_new_schedule_against_new_duration(self):
        service = self.make_service(duration=30)

        response = self.put_json(f"/api/services/{service.id}", {
            "duration": 120,
            "availability": [{"date": iso(self.d1), "times": ["22:30"]}],
        })

        self.assertEqual(response.status_code, 400, response.content)
        service.refresh_from_db()
        self.assertEqual(service.duration, 30)
        self.assertEqual(service.availability, [])

    def test_update_checks_new_schedule_against_current_duration(self):
        service = self.make_service(duration=90)

        response = self.put_json(f"/api/services/{service.id}", {
            "availability": [{"date": iso(self.d1), "times": ["23:00"]}],
        })

        self.assertEqual(response.status_code, 400, response.content)

    def test_duration_change_overflowing_stored_schedule_is_rejected(self):
        schedule = [{"date": iso(self.d1), "times": ["10:00", "23:00"]}]
        service = self.make_service(duration=30, availability=schedule)

        response = self.put_json(f"/api/services/{service.id}", {"duration": 90})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("23:59", response.json()["detail"])
        service.refresh_from_db()
        self.assertEqual(service.duration, 30)
        self.assertEqual(service.availability, schedule)

    def test_duration_change_that_fits_stored_schedule_is_accepted(self):
        schedule = [{"date": iso(self.d1), "times": ["10:00", "22:00"]}]
        service = self.make_service(duration=30, availability=schedule)

        response = self.put_json(f"/api/services/{service.id}", {"duration": 90})

        self.assertEqual(response.status_code, 200, response.content)
        service.refresh_from_db()
        self.assertEqual(service.duration, 90)
        self.assertEqual(service.availability, schedule)

    def test_update_by_other_user_is_forbidden(self):
        service = self.make_service()

        response = self.put_json(
            f"/api/services/{service.id}",
            {"availability": [{"date": iso(self.d1), "times": ["10:00"]}]},
            user=self.other,
        )

        self.assertEqual(response.status_code, 403)
        service.refresh_from_db()
        self.assertEqual(service.availability, [])

    def test_read_endpoints_return_availability(self):
        schedule = [{"date": iso(self.d1), "times": ["10:00", "12:00"]}]
        scheduled = self.make_service(title="A scheduled", availability=schedule)
        plain = self.make_service(title="B plain")

        detail = self.get(f"/api/services/{scheduled.id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["availability"], schedule)
        self.assertEqual(self.get(f"/api/services/{plain.id}").json()["availability"], [])

        for url in ("/api/services/", f"/api/services/business/{self.business.id}"):
            with self.subTest(url=url):
                response = self.get(url)
                self.assertEqual(response.status_code, 200)
                by_id = {item["id"]: item for item in response.json()}
                self.assertEqual(by_id[scheduled.id]["availability"], schedule)
                self.assertEqual(by_id[plain.id]["availability"], [])

        search = self.get("/api/services/search", {"q": "scheduled"})
        self.assertEqual(search.json()[0]["availability"], schedule)

    def test_openapi_documents_availability(self):
        schema = self.get("/api/openapi.json").json()
        components = schema["components"]["schemas"]

        for name in ("ServiceCreateSchema", "ServiceUpdateSchema", "ServiceOutSchema", "ServiceListSchema"):
            with self.subTest(schema=name):
                field = components[name]["properties"]["availability"]
                self.assertIn("working hours", field["description"])

        self.assertEqual(
            components["ServiceScheduleDaySchema"]["properties"]["date"]["format"], "date"
        )
        availability_op = schema["paths"]["/api/services/{service_id}/availability"]["get"]
        self.assertTrue(availability_op["summary"])
        self.assertIn("404", availability_op["responses"])
        dates_op = schema["paths"]["/api/services/{service_id}/available-dates"]["get"]
        self.assertIn("400", dates_op["responses"])


class ServiceScheduleSlotsTests(ServiceAvailabilityTestBase):

    def slots(self, service, day, **params):
        response = self.get(
            f"/api/services/{service.id}/availability", {"date": iso(day), **params}
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["slots"]

    def test_schedule_mode_returns_only_listed_times(self):
        # Working hours 09:00-18:00 must not add slots to a scheduled service
        self.set_working_hours(self.d1, time(9), time(18))
        service = self.make_service(duration=45, availability=[
            {"date": iso(self.d1), "times": ["10:00", "13:30"]},
        ])

        slots = self.slots(service, self.d1)

        self.assertEqual(slots, [
            {"start_time": "10:00", "end_time": "10:45", "available_spots": 1, "is_available": True},
            {"start_time": "13:30", "end_time": "14:15", "available_spots": 1, "is_available": True},
        ])

    def test_schedule_mode_ignores_working_hours(self):
        # Outside working hours on d1, and d2 is a closed day
        self.set_working_hours(self.d1, time(9), time(18))
        self.set_working_hours(self.d2, time(9), time(18), is_closed=True)
        service = self.make_service(duration=60, availability=[
            {"date": iso(self.d1), "times": ["06:00", "21:00"]},
            {"date": iso(self.d2), "times": ["12:00"]},
        ])

        self.assertEqual(
            [(s["start_time"], s["end_time"]) for s in self.slots(service, self.d1)],
            [("06:00", "07:00"), ("21:00", "22:00")],
        )
        self.assertEqual(
            [s["start_time"] for s in self.slots(service, self.d2)], ["12:00"]
        )

    def test_schedule_mode_on_day_without_working_hours(self):
        # The business has no working hours at all
        service = self.make_service(availability=[{"date": iso(self.d1), "times": ["10:00"]}])

        self.assertEqual([s["start_time"] for s in self.slots(service, self.d1)], ["10:00"])

    def test_unlisted_date_and_day_off_have_no_slots(self):
        self.set_working_hours(self.d2, time(9), time(18))
        self.set_working_hours(self.d3, time(9), time(18))
        service = self.make_service(availability=[
            {"date": iso(self.d1), "times": ["10:00"]},
            {"date": iso(self.d3), "times": []},
        ])

        self.assertEqual(self.slots(service, self.d2), [])
        self.assertEqual(self.slots(service, self.d3), [])

    def test_blocked_date_has_no_slots(self):
        service = self.make_service(availability=[{"date": iso(self.d1), "times": ["10:00"]}])
        BlockedDate.objects.create(business=self.business, date=self.d1, reason="Holiday")

        self.assertEqual(self.slots(service, self.d1), [])

    def test_past_date_has_no_slots(self):
        yesterday = self.today - timedelta(days=1)
        service = self.make_service(availability=[{"date": iso(yesterday), "times": ["10:00"]}])

        self.assertEqual(self.slots(service, yesterday), [])

    def test_capacity_counts_existing_bookings(self):
        service = self.make_service(duration=60, capacity=3, availability=[
            {"date": iso(self.d1), "times": ["10:00", "10:30", "12:00"]},
        ])
        self.book(service, self.d1, time(10), time(11), guests=2)
        self.book(service, self.d1, time(12), time(13), guests=3)
        # Cancelled bookings don't take places
        self.book(service, self.d1, time(10), time(11), guests=1, status="cancelled")

        slots = {s["start_time"]: s for s in self.slots(service, self.d1)}

        self.assertEqual(slots["10:00"]["available_spots"], 1)
        # 10:30-11:30 overlaps the 10:00-11:00 booking
        self.assertEqual(slots["10:30"]["available_spots"], 1)
        self.assertEqual(slots["12:00"]["available_spots"], 0)
        self.assertFalse(slots["12:00"]["is_available"])
        self.assertTrue(slots["10:00"]["is_available"])

    def test_unknown_staff_is_404(self):
        service = self.make_service(availability=[{"date": iso(self.d1), "times": ["10:00"]}])

        response = self.get(
            f"/api/services/{service.id}/availability", {"date": iso(self.d1), "staff_id": 999999}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Staff not found")

    def test_unknown_service_is_404(self):
        response = self.get("/api/services/999999/availability", {"date": iso(self.d1)})

        self.assertEqual(response.status_code, 404)

    def test_service_function_keeps_response_shape(self):
        # GET /api/bookings/available-slots relies on this shape
        service = self.make_service(duration=30, capacity=2, availability=[
            {"date": iso(self.d1), "times": ["09:15"]},
        ])

        result = get_service_availability(service, self.d1)

        self.assertEqual(result, {
            "service_id": service.id,
            "date": self.d1,
            "duration": 30,
            "capacity": 2,
            "slots": [{
                "start_time": "09:15",
                "end_time": "09:45",
                "available_spots": 2,
                "is_available": True,
            }],
        })

    def test_available_dates_follow_schedule(self):
        # Working hours every day must not make unscheduled dates available
        for offset in range(7):
            self.set_working_hours(self.today + timedelta(days=offset), time(9), time(18))
        service = self.make_service(capacity=1, availability=[
            {"date": iso(self.today - timedelta(days=1)), "times": ["10:00"]},
            {"date": iso(self.d1), "times": ["10:00", "12:00"]},
            {"date": iso(self.d2), "times": ["10:00"]},
            {"date": iso(self.d3), "times": []},
            {"date": iso(self.d4), "times": ["10:00"]},
            {"date": iso(self.today + timedelta(days=30)), "times": ["10:00"]},
        ])
        self.book(service, self.d2, time(10), time(11))  # fully booked
        BlockedDate.objects.create(business=self.business, date=self.d4)

        response = self.get(f"/api/services/{service.id}/available-dates", {"days": 14})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), [{"date": iso(self.d1), "free_slots": 2}])

    def test_available_dates_days_out_of_range(self):
        service = self.make_service()

        for days in (0, 61):
            with self.subTest(days=days):
                response = self.get(f"/api/services/{service.id}/available-dates", {"days": days})
                self.assertEqual(response.status_code, 400)

    def test_cleared_schedule_falls_back_to_working_hours(self):
        self.set_working_hours(self.d1, time(9), time(11))
        service = self.make_service(availability=[{"date": iso(self.d1), "times": ["15:00"]}])

        self.put_json(f"/api/services/{service.id}", {"availability": []})

        self.assertEqual(
            [s["start_time"] for s in self.slots(service, self.d1)], ["09:00", "10:00"]
        )


class ServiceWorkingHoursFallbackTests(ServiceAvailabilityTestBase):
    """Services without their own schedule behave as before."""

    def test_slots_follow_working_hours(self):
        self.set_working_hours(self.d1, time(9), time(12))
        service = self.make_service(duration=60, capacity=2)
        self.book(service, self.d1, time(10), time(11), guests=2)

        response = self.get(f"/api/services/{service.id}/availability", {"date": iso(self.d1)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"], [
            {"start_time": "09:00", "end_time": "10:00", "available_spots": 2, "is_available": True},
            {"start_time": "10:00", "end_time": "11:00", "available_spots": 0, "is_available": False},
            {"start_time": "11:00", "end_time": "12:00", "available_spots": 2, "is_available": True},
        ])

    def test_closed_or_missing_working_hours_have_no_slots(self):
        self.set_working_hours(self.d1, time(9), time(12), is_closed=True)
        service = self.make_service()

        for day in (self.d1, self.d2):
            with self.subTest(day=day):
                response = self.get(f"/api/services/{service.id}/availability", {"date": iso(day)})
                self.assertEqual(response.json()["slots"], [])

    def test_available_dates_follow_working_hours(self):
        self.set_working_hours(self.d1, time(9), time(11))
        self.set_working_hours(self.d2, time(9), time(10))
        self.set_working_hours(self.d3, time(9), time(11))
        service = self.make_service(duration=60)
        self.book(service, self.d2, time(9), time(10))
        BlockedDate.objects.create(business=self.business, date=self.d3)

        response = self.get(f"/api/services/{service.id}/available-dates", {"days": 4})

        self.assertEqual(response.status_code, 200)
        # Today's weekday has no working hours; d2 is full, d3 blocked
        self.assertEqual(response.json(), [{"date": iso(self.d1), "free_slots": 2}])


class FarFutureDateTests(ServiceAvailabilityTestBase):
    """
    Slot ends are computed in minutes: datetime + timedelta overflows on
    9999-12-31 (or with a huge duration) and used to give a 500.
    """

    def test_normalize_rejects_slot_crossing_midnight_on_last_date(self):
        with self.assertRaisesMessage(ValueError, "Slot at 23:30 on 9999-12-31 would end after 23:59"):
            normalize_availability([{"date": "9999-12-31", "times": ["23:30"]}], duration=60)

    def test_normalize_accepts_fitting_slot_on_last_date(self):
        self.assertEqual(
            normalize_availability([{"date": "9999-12-31", "times": ["23:00"]}], duration=59),
            [{"date": "9999-12-31", "times": ["23:00"]}],
        )

    def test_normalize_with_huge_duration_is_value_error(self):
        with self.assertRaisesMessage(ValueError, "would end after 23:59"):
            normalize_availability([{"date": iso(self.d1), "times": ["00:00"]}], duration=10 ** 9)

    def test_api_create_crossing_midnight_on_last_date_is_400(self):
        response = self.post_json("/api/services/create", self.create_payload(
            duration=120,
            availability=[{"date": "9999-12-31", "times": ["22:30"]}],
        ))

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(
            response.json()["detail"], "Slot at 22:30 on 9999-12-31 would end after 23:59"
        )
        self.assertFalse(Service.objects.exists())

    def test_api_update_duration_on_last_date_is_400(self):
        schedule = [{"date": "9999-12-31", "times": ["23:00"]}]
        service = self.make_service(duration=30, availability=schedule)

        response = self.put_json(f"/api/services/{service.id}", {"duration": 120})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("23:59", response.json()["detail"])
        service.refresh_from_db()
        self.assertEqual(service.duration, 30)

    def test_model_clean_on_last_date_is_validation_error(self):
        # Service.clean() is what the admin runs
        service = Service(
            business=self.business, title="Late", description="Late class", category="fitness",
            duration=60, price="1.00",
            availability=[{"date": "9999-12-31", "times": ["23:30"]}],
        )

        with self.assertRaises(ValidationError) as ctx:
            service.full_clean()

        self.assertIn("23:59", ctx.exception.message_dict["availability"][0])

    def test_admin_form_on_last_date_shows_error(self):
        from core.admin import ServiceAdminForm

        form = ServiceAdminForm(data={
            "business": self.business.id,
            "title": "Late",
            "description": "Late class",
            "category": "fitness",
            "duration": 60,
            "capacity": 1,
            "price": "1.00",
            "availability": '[{"date": "9999-12-31", "times": ["23:30"]}]',
            "is_active": "on",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("23:59", form.errors["availability"][0])

    def test_slots_on_last_date(self):
        scheduled = self.make_service(
            title="A", duration=60, availability=[{"date": "9999-12-31", "times": ["10:00", "22:59"]}],
        )
        # Working hours until midnight, and a slot longer than the day
        self.set_working_hours(FAR_FUTURE, time(9), time(0))
        long_one = self.make_service(title="B", duration=1000)
        hourly = self.make_service(title="C", duration=60)

        response = self.get(f"/api/services/{scheduled.id}/availability", {"date": "9999-12-31"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [(s["start_time"], s["end_time"]) for s in response.json()["slots"]],
            [("10:00", "11:00"), ("22:59", "23:59")],
        )

        response = self.get(f"/api/services/{long_one.id}/availability", {"date": "9999-12-31"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["slots"], [])

        # 09:00-23:59 holds 14 whole hours
        response = self.get(f"/api/services/{hourly.id}/availability", {"date": "9999-12-31"})
        self.assertEqual(response.status_code, 200, response.content)
        slots = response.json()["slots"]
        self.assertEqual(len(slots), 14)
        self.assertEqual((slots[-1]["start_time"], slots[-1]["end_time"]), ("22:00", "23:00"))


class ZeroDurationTests(ServiceAvailabilityTestBase):
    """
    duration=0 fits PositiveIntegerField but used to make the working-hours
    generator loop forever. Generator calls go through call_with_trace_budget
    first, so a regression fails here instead of hanging the suite.
    """

    def zero_service(self, availability=None):
        # Saved through the ORM, which skips Service.clean()
        return self.make_service(title="Zero", duration=0, availability=availability)

    def assert_generators_give_no_slots(self, service, day):
        hours = WorkingHours(
            business=self.business, day_of_week=day.weekday(), open_time=time(9), close_time=time(18),
        )
        self.assertEqual(call_with_trace_budget(_working_hours_slots, service, day, hours), [])
        if service.availability:
            self.assertEqual(call_with_trace_budget(schedule_slots, service, day), [])

    def test_model_clean_rejects_zero_duration(self):
        service = Service(
            business=self.business, title="Zero", description="Zero", category="fitness",
            duration=0, price="1.00", availability=[{"date": iso(self.d1), "times": ["10:00"]}],
        )

        with self.assertRaises(ValidationError) as ctx:
            service.full_clean()

        self.assertEqual(
            ctx.exception.message_dict, {"duration": ["Duration must be at least 1 minute"]}
        )

    def test_admin_form_rejects_zero_duration(self):
        from core.admin import ServiceAdminForm

        form = ServiceAdminForm(data={
            "business": self.business.id,
            "title": "Zero",
            "description": "Zero",
            "category": "fitness",
            "duration": 0,
            "capacity": 1,
            "price": "1.00",
            "availability": "[]",
            "is_active": "on",
        })

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["duration"], ["Duration must be at least 1 minute"])

    def test_generators_give_no_slots(self):
        self.assert_generators_give_no_slots(self.zero_service(), self.d1)
        self.assert_generators_give_no_slots(
            self.zero_service(availability=[{"date": iso(self.d1), "times": ["10:00"]}]), self.d1
        )

    def test_endpoints_with_zero_duration(self):
        plain = self.zero_service()
        scheduled = self.zero_service(availability=[{"date": iso(self.d1), "times": ["10:00"]}])
        for offset in range(7):
            self.set_working_hours(self.today + timedelta(days=offset), time(9), time(18))
        # The requests below are only reached when the generators terminate
        self.assert_generators_give_no_slots(plain, self.d1)
        self.assert_generators_give_no_slots(scheduled, self.d1)

        for service in (plain, scheduled):
            with self.subTest(scheduled=bool(service.availability)):
                response = self.get(f"/api/services/{service.id}/availability", {"date": iso(self.d1)})
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["slots"], [])

                response = self.get(f"/api/services/{service.id}/available-dates", {"days": 7})
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json(), [])

                response = self.get("/api/bookings/available-slots", {
                    "business_id": self.business.id,
                    "service_id": service.id,
                    "branch_id": self.branch.id,
                    "date": iso(self.d1),
                })
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["slots"], [])
