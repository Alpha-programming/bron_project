from datetime import time, timedelta
from decimal import Decimal

from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Booking,
    Branch,
    Business,
    Category,
    Product,
    Service,
    Staff,
    User,
    WorkingHours,
)
from core.utils.jwt import create_access_token

SLOTS_URL = "/api/bookings/available-slots"


def make_user(name, n):
    return User.objects.create_user(
        username=name,
        email=f"{name}@bron.test",
        phone=f"+99890000{n:04d}",
        password="Pass12345!",
    )


def make_business(owner, name, n):
    return Business.objects.create(
        owner=owner,
        name=name,
        category=Category.objects.get(slug="gym"),
        address="Tashkent",
        phone=f"+99871000{n:04d}",
        is_active=True,
    )


def make_service(business, title, price, **extra):
    fields = {"description": "", "category": "gym", "duration": 60, "capacity": 2}
    fields.update(extra)
    return Service.objects.create(business=business, title=title, price=Decimal(price), **fields)


class BookingApiTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user("owner", 1)
        cls.customer = make_user("customer", 2)

        cls.business = make_business(cls.owner, "Iron Gym", 1)
        cls.branch = Branch.objects.create(business=cls.business, name="Main", address="A", phone="1")
        cls.staff = Staff.objects.create(business=cls.business, full_name="Coach", position="Coach")

        cls.service = make_service(cls.business, "Training", "95000.00")
        cls.extra_service = make_service(cls.business, "Massage", "50000.00")
        cls.inactive_service = make_service(cls.business, "Old", "1000.00", is_active=False)
        cls.product = Product.objects.create(business=cls.business, name="Water", price=Decimal("10000.00"))
        cls.product2 = Product.objects.create(business=cls.business, name="Towel", price=Decimal("5000.50"))
        cls.inactive_product = Product.objects.create(
            business=cls.business, name="Gone", price=Decimal("1.00"), is_active=False
        )

        other = make_business(make_user("other", 3), "Other Gym", 2)
        cls.other_branch = Branch.objects.create(business=other, name="Other", address="B", phone="2")
        cls.other_staff = Staff.objects.create(business=other, full_name="Stranger", position="Coach")
        cls.other_service = make_service(other, "Foreign", "1.00")
        cls.other_product = Product.objects.create(business=other, name="Foreign", price=Decimal("1.00"))

        for weekday in range(7):
            WorkingHours.objects.create(
                business=cls.business, day_of_week=weekday, open_time=time(9), close_time=time(18)
            )

        cls.day = timezone.localdate() + timedelta(days=3)

        # Own schedule: 10:00 inside and 20:00 outside the 09-18 working hours
        cls.scheduled = make_service(
            cls.business,
            "Yoga",
            "70000.00",
            availability=[{"date": cls.day.isoformat(), "times": ["10:00", "20:00"]}],
        )

    def auth(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}

    def book(self, user=None, **overrides):
        body = {
            "business_id": self.business.id,
            "service_id": self.service.id,
            "branch_id": self.branch.id,
            "booking_date": self.day.isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
        }
        body.update(overrides)
        return self.client.post(
            "/api/bookings/create",
            body,
            content_type="application/json",
            secure=True,
            **self.auth(user or self.customer),
        )

    def reschedule(self, booking_id, start, end, day=None, user=None):
        return self.client.patch(
            f"/api/bookings/{booking_id}/reschedule",
            {"booking_date": (day or self.day).isoformat(), "start_time": start, "end_time": end},
            content_type="application/json",
            secure=True,
            **self.auth(user or self.customer),
        )

    def get(self, url, user=None, **params):
        extra = self.auth(user) if user else {}
        return self.client.get(url, params, secure=True, **extra)


class BookingItemsTests(BookingApiTestCase):

    def test_server_prices_used_and_client_name_price_ignored(self):
        response = self.book(items=[
            {"id": self.service.id, "kind": "service", "quantity": 1, "name": "Cheap", "price": "1.00"},
            {"id": self.product.id, "kind": "product", "quantity": 2, "name": "Gold", "price": 1},
        ])

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["total_price"], 115000.0)
        self.assertEqual(data["items"], [
            {"id": self.service.id, "name": "Training", "price": 95000.0, "quantity": 1, "kind": "service"},
            {"id": self.product.id, "name": "Water", "price": 10000.0, "quantity": 2, "kind": "product"},
        ])

        booking = Booking.objects.get(id=data["id"])
        self.assertEqual(booking.total_price, Decimal("115000.00"))
        self.assertEqual(booking.items[0]["price"], "95000.00")
        self.assertEqual(booking.items[1]["price"], "10000.00")
        self.assertEqual(list(booking.products.all()), [self.product])

    def test_duplicates_merged(self):
        response = self.book(items=[
            {"id": self.product.id, "kind": "product", "quantity": 1},
            {"id": self.extra_service.id, "kind": "service"},
            {"id": self.product.id, "kind": "product", "quantity": 2},
            {"id": self.extra_service.id, "kind": "service"},
        ])

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(
            [(i["kind"], i["id"], i["quantity"]) for i in data["items"]],
            [
                ("service", self.service.id, 1),
                ("product", self.product.id, 3),
                ("service", self.extra_service.id, 2),
            ],
        )
        self.assertEqual(data["total_price"], 95000 + 3 * 10000 + 2 * 50000)

    def test_booked_service_added_when_missing(self):
        response = self.book(items=[{"id": self.product2.id, "kind": "product"}])

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["items"][0], {
            "id": self.service.id, "name": "Training", "price": 95000.0, "quantity": 1, "kind": "service",
        })
        self.assertEqual(data["items"][1]["price"], 5000.5)
        self.assertEqual(data["total_price"], 100000.5)
        self.assertEqual(Booking.objects.get().total_price, Decimal("100000.50"))

    def test_booked_service_quantity_from_items_kept(self):
        response = self.book(items=[{"id": self.service.id, "kind": "service", "quantity": 2}])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["items"],
            [{"id": self.service.id, "name": "Training", "price": 95000.0, "quantity": 2, "kind": "service"}],
        )
        self.assertEqual(response.json()["total_price"], 190000.0)

    def test_foreign_or_inactive_item_rejected_without_booking(self):
        cases = [
            ("product", self.other_product.id),
            ("product", self.inactive_product.id),
            ("product", 999999),
            ("service", self.other_service.id),
            ("service", self.inactive_service.id),
        ]

        for kind, item_id in cases:
            with self.subTest(kind=kind, id=item_id):
                response = self.book(items=[
                    {"id": self.product.id, "kind": "product"},
                    {"id": item_id, "kind": kind},
                ])

                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()["detail"], f"Item not found: {kind} {item_id}")
                self.assertFalse(Booking.objects.exists())

    def test_merged_quantity_over_limit_rejected(self):
        response = self.book(items=[
            {"id": self.product.id, "kind": "product", "quantity": 60},
            {"id": self.product.id, "kind": "product", "quantity": 60},
        ])

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Booking.objects.exists())

    def test_quantity_out_of_range_is_422(self):
        for quantity in (0, 101):
            with self.subTest(quantity=quantity):
                response = self.book(items=[{"id": self.product.id, "kind": "product", "quantity": quantity}])
                self.assertEqual(response.status_code, 422)

        response = self.book(items=[{"id": self.product.id, "kind": "gift"}])
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Booking.objects.exists())

    def test_legacy_product_ids_fill_items(self):
        response = self.book(product_ids=[
            self.product.id, self.product2.id, self.other_product.id, self.product.id,
        ])

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(
            [(i["kind"], i["id"], i["quantity"]) for i in data["items"]],
            [
                ("service", self.service.id, 1),
                ("product", self.product.id, 1),
                ("product", self.product2.id, 1),
            ],
        )
        self.assertEqual(data["total_price"], 110000.5)

        booking = Booking.objects.get()
        self.assertEqual(set(booking.products.all()), {self.product, self.product2})

    def test_no_items_no_products_charges_service(self):
        response = self.book()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total_price"], 95000.0)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertFalse(Booking.objects.get().products.exists())

    def test_product_ids_ignored_when_items_sent(self):
        response = self.book(
            items=[{"id": self.product.id, "kind": "product"}],
            product_ids=[self.product2.id],
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [i["id"] for i in response.json()["items"] if i["kind"] == "product"],
            [self.product.id],
        )
        self.assertEqual(list(Booking.objects.get().products.all()), [self.product])

    def test_items_returned_when_reading_bookings(self):
        created = self.book(items=[{"id": self.product.id, "kind": "product", "quantity": 2}]).json()
        expected = [
            {"id": self.service.id, "name": "Training", "price": 95000.0, "quantity": 1, "kind": "service"},
            {"id": self.product.id, "name": "Water", "price": 10000.0, "quantity": 2, "kind": "product"},
        ]
        self.assertEqual(created["items"], expected)

        # Prices are a snapshot: later price changes don't rewrite the order
        Product.objects.filter(id=self.product.id).update(price=Decimal("99999.00"))

        detail = self.get(f"/api/bookings/{created['id']}", user=self.customer)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["items"], expected)

        mine = self.get("/api/bookings/my", user=self.customer)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json()[0]["items"], expected)
        self.assertEqual(mine.json()[0]["total_price"], 115000.0)

        business = self.get(f"/api/bookings/business/{self.business.id}", user=self.owner)
        self.assertEqual(business.status_code, 200)
        self.assertEqual(business.json()[0]["items"], expected)


class BookingScheduleTests(BookingApiTestCase):

    def book_scheduled(self, start, end, day=None):
        return self.book(
            service_id=self.scheduled.id,
            booking_date=(day or self.day).isoformat(),
            start_time=start,
            end_time=end,
        )

    def test_create_on_unlisted_date_rejected(self):
        response = self.book_scheduled("10:00", "11:00", day=self.day + timedelta(days=1))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Service is not available on this date")

    def test_create_at_unlisted_time_rejected(self):
        response = self.book_scheduled("11:00", "12:00")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Selected time is not in the service schedule")

    def test_create_with_wrong_end_time_rejected(self):
        response = self.book_scheduled("10:00", "10:30")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "end_time must be 11:00 for the 10:00 slot")
        self.assertFalse(Booking.objects.exists())

    def test_create_at_scheduled_time(self):
        for start, end in (("10:00", "11:00"), ("20:00", "21:00")):
            with self.subTest(start=start):
                response = self.book_scheduled(start, end)
                self.assertEqual(response.status_code, 200, response.content)

        self.assertEqual(Booking.objects.count(), 2)

    def test_service_without_schedule_unchanged(self):
        response = self.book(start_time="12:30", end_time="13:15")

        self.assertEqual(response.status_code, 200, response.content)

    def test_reschedule_to_scheduled_time_outside_working_hours(self):
        booking_id = self.book_scheduled("10:00", "11:00").json()["id"]

        response = self.reschedule(booking_id, "20:00", "21:00")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["start_time"], "20:00:00")

    def test_reschedule_to_unscheduled_time_rejected(self):
        booking_id = self.book_scheduled("10:00", "11:00").json()["id"]

        # Inside working hours but not in the service schedule
        response = self.reschedule(booking_id, "12:00", "13:00")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Selected time is not in the service schedule")

        response = self.reschedule(booking_id, "10:00", "11:00", day=self.day + timedelta(days=1))
        self.assertEqual(response.status_code, 400)

        booking = Booking.objects.get(id=booking_id)
        self.assertEqual(booking.start_time, time(10))

    def test_reschedule_without_schedule_keeps_working_hours_check(self):
        booking_id = self.book().json()["id"]

        response = self.reschedule(booking_id, "20:00", "21:00")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Time must be within working hours 09:00-18:00")


class AvailableSlotsTests(BookingApiTestCase):

    def slots(self, **params):
        query = {
            "business_id": self.business.id,
            "service_id": self.service.id,
            "branch_id": self.branch.id,
            "date": self.day.isoformat(),
        }
        query.update(params)
        return self.get(SLOTS_URL, **{k: v for k, v in query.items() if v is not None})

    def test_response_shape(self):
        response = self.slots()

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["business_id"], self.business.id)
        self.assertEqual(data["service_id"], self.service.id)
        self.assertEqual(data["branch_id"], self.branch.id)
        self.assertIsNone(data["staff_id"])
        self.assertEqual(data["date"], self.day.isoformat())
        self.assertEqual(data["duration"], 60)
        self.assertEqual(data["capacity"], 2)

        # 09:00-18:00 in 60-minute slots
        self.assertEqual(len(data["slots"]), 9)
        self.assertEqual(data["slots"][0], {
            "start_time": "09:00", "end_time": "10:00", "is_available": True, "available_spots": 2,
        })
        self.assertEqual(data["slots"][-1]["end_time"], "18:00")

    def test_staff_id_optional_and_echoed(self):
        response = self.slots(staff_id=self.staff.id)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["staff_id"], self.staff.id)

    def test_foreign_or_unknown_ids_are_404(self):
        cases = {
            "business": {"business_id": 999999},
            "service": {"service_id": self.other_service.id},
            "branch": {"branch_id": self.other_branch.id},
            "staff": {"staff_id": self.other_staff.id},
        }

        for name, params in cases.items():
            with self.subTest(name):
                response = self.slots(**params)
                self.assertEqual(response.status_code, 404)
                self.assertIn("not found", response.json()["detail"])

    def test_date_required(self):
        response = self.get(SLOTS_URL, business_id=self.business.id, service_id=self.service.id,
                            branch_id=self.branch.id, target_date=self.day.isoformat())
        self.assertEqual(response.status_code, 422)

        response = self.slots(date="01.10.2026")
        self.assertEqual(response.status_code, 422)

    def test_inactive_business_has_no_slots(self):
        Business.objects.filter(id=self.business.id).update(is_active=False)

        response = self.slots()

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["slots"], [])
        self.assertEqual(response.json()["business_id"], self.business.id)

    def test_service_schedule_respected(self):
        response = self.slots(service_id=self.scheduled.id)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [(s["start_time"], s["end_time"]) for s in response.json()["slots"]],
            [("10:00", "11:00"), ("20:00", "21:00")],
        )

        other_day = self.slots(service_id=self.scheduled.id, date=(self.day + timedelta(days=1)).isoformat())
        self.assertEqual(other_day.json()["slots"], [])

    def test_capacity_counted(self):
        def slot_at(start):
            slots = self.slots().json()["slots"]
            return next(s for s in slots if s["start_time"] == start)

        self.assertEqual(self.book(guest_count=1).status_code, 200)
        self.assertEqual(slot_at("10:00"), {
            "start_time": "10:00", "end_time": "11:00", "is_available": True, "available_spots": 1,
        })

        self.assertEqual(self.book(guest_count=1).status_code, 200)
        self.assertEqual(slot_at("10:00")["available_spots"], 0)
        self.assertFalse(slot_at("10:00")["is_available"])
        self.assertEqual(slot_at("11:00")["available_spots"], 2)

        # A full slot can't be booked
        self.assertEqual(self.book(guest_count=1).status_code, 400)


class StaffAvailabilityTests(BookingApiTestCase):
    """
    One rule for slots and bookings: places are counted over all bookings of
    the service; a chosen staff member is also busy with their bookings in
    any service.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff2 = Staff.objects.create(business=cls.business, full_name="Coach 2", position="Coach")
        cls.staff3 = Staff.objects.create(business=cls.business, full_name="Coach 3", position="Coach")

    def existing(self, service, start, end, staff=None, guests=1, status="confirmed"):
        return Booking.objects.create(
            user=self.customer,
            business=self.business,
            service=service,
            branch=self.branch,
            staff=staff,
            booking_date=self.day,
            start_time=start,
            end_time=end,
            guest_count=guests,
            status=status,
        )

    def slots(self, staff=None, service=None):
        params = {
            "business_id": self.business.id,
            "service_id": (service or self.service).id,
            "branch_id": self.branch.id,
            "date": self.day.isoformat(),
        }
        if staff is not None:
            params["staff_id"] = staff.id
        response = self.get(SLOTS_URL, **params)
        self.assertEqual(response.status_code, 200, response.content)
        return {s["start_time"]: s for s in response.json()["slots"]}

    def service_slots(self, staff=None):
        params = {"date": self.day.isoformat()}
        if staff is not None:
            params["staff_id"] = staff.id
        response = self.get(f"/api/services/{self.service.id}/availability", **params)
        self.assertEqual(response.status_code, 200, response.content)
        return {s["start_time"]: s for s in response.json()["slots"]}

    def test_capacity_counted_across_staff(self):
        # Capacity 2: one guest with each of two staff members fills 10:00
        self.existing(self.service, time(10), time(11), staff=self.staff)
        self.existing(self.service, time(10), time(11), staff=self.staff2)
        self.existing(self.service, time(12), time(13), staff=self.staff2)

        for staff in (None, self.staff3):
            with self.subTest(staff=staff):
                for slots in (self.slots(staff), self.service_slots(staff)):
                    self.assertEqual(slots["10:00"]["available_spots"], 0)
                    self.assertFalse(slots["10:00"]["is_available"])
                    # Another staff member's booking still takes a place
                    self.assertEqual(slots["12:00"]["available_spots"], 1)
                    self.assertTrue(slots["12:00"]["is_available"])

        # Booking agrees: a free staff member doesn't add places
        response = self.book(staff_id=self.staff3.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Only 0 places left for this time")

    def test_staff_busy_in_other_service_blocks_slot_only_with_staff_id(self):
        # 12:30-13:30 in another service overlaps the 12:00 and 13:00 slots
        self.existing(self.extra_service, time(12, 30), time(13, 30), staff=self.staff)
        # Inactive bookings don't make anyone busy
        self.existing(self.extra_service, time(15), time(16), staff=self.staff, status="cancelled")

        for slots in (self.slots(), self.service_slots(), self.slots(self.staff2)):
            self.assertTrue(all(s["is_available"] and s["available_spots"] == 2 for s in slots.values()))

        for slots in (self.slots(self.staff), self.service_slots(self.staff)):
            for start in ("12:00", "13:00"):
                self.assertEqual(slots[start]["available_spots"], 0)
                self.assertFalse(slots[start]["is_available"])
            for start in ("11:00", "14:00", "15:00"):
                self.assertEqual(slots[start]["available_spots"], 2)
                self.assertTrue(slots[start]["is_available"])

        dates_url = f"/api/services/{self.service.id}/available-dates"
        free = {d["date"]: d["free_slots"] for d in self.get(dates_url, days=5).json()}
        self.assertEqual(free[self.day.isoformat()], 9)
        free = {d["date"]: d["free_slots"] for d in self.get(dates_url, days=5, staff_id=self.staff.id).json()}
        self.assertEqual(free[self.day.isoformat()], 7)

    def test_create_with_busy_staff_is_400(self):
        self.existing(self.extra_service, time(10), time(11), staff=self.staff)

        response = self.book(staff_id=self.staff.id, start_time="10:30", end_time="11:30")

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(
            response.json()["detail"], "Selected time is not available: staff member is busy"
        )
        self.assertEqual(Booking.objects.count(), 1)

        # Same time with another staff member or without one is fine
        self.assertEqual(self.book(staff_id=self.staff2.id, start_time="10:30", end_time="11:30").status_code, 200)
        self.assertEqual(self.book(start_time="10:30", end_time="11:30").status_code, 200)
        # Right after the busy time is fine too (other service: 11:00 here is full now)
        response = self.book(
            service_id=self.extra_service.id, staff_id=self.staff.id, start_time="11:00", end_time="12:00",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_create_ignores_inactive_bookings_of_staff(self):
        for status in ("cancelled", "rejected", "completed"):
            self.existing(self.extra_service, time(10), time(11), staff=self.staff, status=status)

        response = self.book(staff_id=self.staff.id)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["staff_id"], self.staff.id)

    def test_every_slot_shown_for_staff_matches_booking_result(self):
        self.existing(self.service, time(9), time(10), staff=self.staff2, guests=2)    # full
        self.existing(self.service, time(10), time(11), staff=self.staff2)             # 1 left
        self.existing(self.extra_service, time(12, 30), time(13, 30), staff=self.staff)  # busy elsewhere
        self.existing(self.service, time(15), time(16), staff=self.staff)              # 1 left, busy
        self.existing(self.extra_service, time(17), time(18), staff=self.staff, status="cancelled")

        slots = self.slots(self.staff)
        self.assertEqual(slots, self.service_slots(self.staff))
        self.assertEqual(
            {start for start, s in slots.items() if not s["is_available"]},
            {"09:00", "12:00", "13:00", "15:00"},
        )

        for start, slot in slots.items():
            with self.subTest(start=start):
                # Each attempt is rolled back so every slot is checked against the same state
                with transaction.atomic():
                    response = self.book(
                        staff_id=self.staff.id, start_time=slot["start_time"], end_time=slot["end_time"],
                    )
                    transaction.set_rollback(True)

                expected = 200 if slot["is_available"] else 400
                self.assertEqual(response.status_code, expected, response.content)

    def test_reschedule_into_staff_booking_of_other_service_is_409(self):
        booking_id = self.book(staff_id=self.staff.id).json()["id"]
        self.existing(self.extra_service, time(14), time(15), staff=self.staff)

        response = self.reschedule(booking_id, "14:30", "15:30")

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(
            response.json()["detail"], "Selected time is not available: staff member is busy"
        )
        # Moving within its own time range is not a clash with itself
        self.assertEqual(self.reschedule(booking_id, "10:30", "11:30").status_code, 200)

    def test_update_to_busy_staff_is_409(self):
        booking_id = self.book().json()["id"]
        self.existing(self.extra_service, time(10, 30), time(11, 30), staff=self.staff)

        def put(staff):
            return self.client.put(
                f"/api/bookings/{booking_id}",
                {"staff_id": staff.id},
                content_type="application/json",
                secure=True,
                **self.auth(self.customer),
            )

        response = put(self.staff)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(
            response.json()["detail"], "Selected time is not available: staff member is busy"
        )
        self.assertIsNone(Booking.objects.get(id=booking_id).staff_id)

        response = put(self.staff2)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["staff_id"], self.staff2.id)
        # Re-assigning the same staff member is not a clash with the booking itself
        self.assertEqual(put(self.staff2).status_code, 200)


class CorruptedItemsTests(BookingApiTestCase):
    """Booking.items can be edited outside the API; bad rows must not give a 500."""

    VALID = {"id": 7, "name": "Water", "price": "10.50", "quantity": 2, "kind": "product"}

    def make_booking(self, items):
        booking = Booking.objects.create(
            user=self.customer,
            business=self.business,
            service=self.service,
            branch=self.branch,
            staff=self.staff,
            booking_date=self.day,
            start_time=time(10),
            end_time=time(11),
        )
        # update() skips any model-level cleaning, like a manual DB edit
        Booking.objects.filter(id=booking.id).update(items=items)
        return booking

    def read_all(self, booking):
        responses = {
            "my": self.get("/api/bookings/my", user=self.customer),
            "detail": self.get(f"/api/bookings/{booking.id}", user=self.customer),
            "business": self.get(f"/api/bookings/business/{self.business.id}", user=self.owner),
            "staff": self.get(f"/api/bookings/staff/{self.staff.id}", user=self.owner),
        }
        items = {}
        for name, response in responses.items():
            self.assertEqual(response.status_code, 200, f"{name}: {response.content}")
            data = response.json()
            items[name] = data["items"] if name == "detail" else data[0]["items"]
        return items

    def test_malformed_rows_are_skipped_or_defaulted(self):
        booking = self.make_booking([
            self.VALID,
            "not a dict",
            42,
            ["id", 1],
            {"name": "No id", "price": "1.00", "quantity": 1, "kind": "product"},
            {"id": "8", "name": "String id", "price": "1.00", "kind": "product"},
            {"id": True, "name": "Bool id", "price": "1.00", "kind": "product"},
            {"id": 9, "name": "Gift", "price": "1.00", "kind": "gift"},
            {"id": 10, "name": "No kind", "price": "1.00"},
            {"id": 11, "name": "Bad price", "price": "abc", "quantity": 1, "kind": "service"},
            {"id": 12, "name": "NaN price", "price": "NaN", "quantity": 1, "kind": "product"},
            {"id": 13, "name": "List price", "price": [1], "quantity": 1, "kind": "product"},
            {"id": 14, "name": "Zero quantity", "price": 5, "quantity": 0, "kind": "product"},
            {"id": 15, "name": "Text quantity", "price": "5", "quantity": "3", "kind": "product"},
            {"id": 16, "name": "Float quantity", "price": "5", "quantity": 2.5, "kind": "product"},
            {"id": 17, "name": "Negative quantity", "price": "5", "quantity": -4, "kind": "product"},
            {"id": 18, "name": 123, "kind": "product"},
            {"id": 19, "kind": "service"},
        ])

        expected = [
            {"id": 7, "name": "Water", "price": 10.5, "quantity": 2, "kind": "product"},
            {"id": 11, "name": "Bad price", "price": 0.0, "quantity": 1, "kind": "service"},
            {"id": 12, "name": "NaN price", "price": 0.0, "quantity": 1, "kind": "product"},
            {"id": 13, "name": "List price", "price": 0.0, "quantity": 1, "kind": "product"},
            {"id": 14, "name": "Zero quantity", "price": 5.0, "quantity": 1, "kind": "product"},
            {"id": 15, "name": "Text quantity", "price": 5.0, "quantity": 1, "kind": "product"},
            {"id": 16, "name": "Float quantity", "price": 5.0, "quantity": 1, "kind": "product"},
            {"id": 17, "name": "Negative quantity", "price": 5.0, "quantity": 1, "kind": "product"},
            {"id": 18, "name": "", "price": 0.0, "quantity": 1, "kind": "product"},
            {"id": 19, "name": "", "price": 0.0, "quantity": 1, "kind": "service"},
        ]
        for name, items in self.read_all(booking).items():
            with self.subTest(endpoint=name):
                self.assertEqual(items, expected)

    def test_non_list_items_read_as_empty(self):
        for value in ({"id": 1, "kind": "service"}, "garbage", 5, True):
            with self.subTest(items=value):
                Booking.objects.all().delete()
                booking = self.make_booking(value)

                for name, items in self.read_all(booking).items():
                    self.assertEqual(items, [], name)
