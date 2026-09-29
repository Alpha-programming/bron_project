import importlib
from datetime import time, timedelta
from decimal import Decimal

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from core.models import Booking, Branch, Business, Category, Product, Service, User

# The module name starts with a digit, so a plain import statement can't load it
migration = importlib.import_module("core.migrations.0011_booking_items")


class BackfillItemsTests(TestCase):
    """
    backfill_items rebuilds the order of bookings made before Booking.items
    existed. Prices may have changed since, so the lines must add up to the
    total_price that was actually charged.
    """

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create_user(
            username="owner", email="owner@bron.test", phone="+998900000201", password="Pass12345!",
        )
        cls.customer = User.objects.create_user(
            username="customer", email="customer@bron.test", phone="+998900000202", password="Pass12345!",
        )
        cls.business = Business.objects.create(
            owner=owner,
            name="Iron Gym",
            category=Category.objects.get(slug="gym"),
            address="Tashkent",
            phone="+998710000201",
            is_active=True,
        )
        cls.branch = Branch.objects.create(business=cls.business, name="Main", address="A", phone="1")
        cls.service = Service.objects.create(
            business=cls.business, title="Training", description="", category="gym",
            duration=60, price=Decimal("100.00"),
        )
        cls.water = Product.objects.create(business=cls.business, name="Water", price=Decimal("10.00"))
        cls.towel = Product.objects.create(business=cls.business, name="Towel", price=Decimal("5.50"))

    def make_booking(self, total_price, products=()):
        booking = Booking.objects.create(
            user=self.customer,
            business=self.business,
            service=self.service,
            branch=self.branch,
            booking_date=timezone.localdate() - timedelta(days=30),
            start_time=time(10),
            end_time=time(11),
            total_price=total_price,
        )
        booking.products.set(products)
        return booking

    def set_prices(self, service=None, water=None, towel=None):
        if service is not None:
            Service.objects.filter(id=self.service.id).update(price=Decimal(service))
        if water is not None:
            Product.objects.filter(id=self.water.id).update(price=Decimal(water))
        if towel is not None:
            Product.objects.filter(id=self.towel.id).update(price=Decimal(towel))

    def backfill(self, booking):
        # State right after AddField: every row has the empty default
        Booking.objects.update(items=[])
        migration.backfill_items(apps, None)
        booking.refresh_from_db()
        # Product order from the M2M is not defined, the service line comes first
        return booking.items[:1] + sorted(booking.items[1:], key=lambda line: line["id"])

    def assert_adds_up(self, booking, items):
        total = sum(Decimal(line["price"]) * line["quantity"] for line in items)
        self.assertEqual(total, booking.total_price)

    def test_service_line_gets_the_rest_of_the_charged_total(self):
        # Charged 100 + 10 + 5.50; afterwards the service and water got pricier
        booking = self.make_booking(Decimal("115.50"), [self.water, self.towel])
        self.set_prices(service="150.00", water="12.00")

        items = self.backfill(booking)

        self.assertEqual(items, [
            {"id": self.service.id, "name": "Training", "price": "98.00", "quantity": 1, "kind": "service"},
            {"id": self.water.id, "name": "Water", "price": "12.00", "quantity": 1, "kind": "product"},
            {"id": self.towel.id, "name": "Towel", "price": "5.50", "quantity": 1, "kind": "product"},
        ])
        self.assert_adds_up(booking, items)

    def test_booking_without_products_keeps_charged_service_price(self):
        booking = self.make_booking(Decimal("80.00"))
        self.set_prices(service="100.00")

        items = self.backfill(booking)

        self.assertEqual(items, [
            {"id": self.service.id, "name": "Training", "price": "80.00", "quantity": 1, "kind": "service"},
        ])
        self.assert_adds_up(booking, items)

    def test_unchanged_prices_give_current_prices(self):
        booking = self.make_booking(Decimal("110.00"), [self.water])

        items = self.backfill(booking)

        self.assertEqual([line["price"] for line in items], ["100.00", "10.00"])
        self.assert_adds_up(booking, items)

    def test_products_dearer_than_total_fall_back_to_current_service_price(self):
        # 20 charged, but the products alone now cost 25.50
        booking = self.make_booking(Decimal("20.00"), [self.water, self.towel])
        self.set_prices(service="120.00", water="20.00")

        items = self.backfill(booking)

        self.assertEqual(items, [
            {"id": self.service.id, "name": "Training", "price": "120.00", "quantity": 1, "kind": "service"},
            {"id": self.water.id, "name": "Water", "price": "20.00", "quantity": 1, "kind": "product"},
            {"id": self.towel.id, "name": "Towel", "price": "5.50", "quantity": 1, "kind": "product"},
        ])

    def test_rest_exactly_zero_is_kept(self):
        booking = self.make_booking(Decimal("15.50"), [self.water, self.towel])

        items = self.backfill(booking)

        self.assertEqual(items[0]["price"], "0.00")
        self.assert_adds_up(booking, items)

    def test_every_booking_is_filled(self):
        first = self.make_booking(Decimal("100.00"))
        second = self.make_booking(Decimal("105.50"), [self.towel])

        Booking.objects.update(items=[])
        migration.backfill_items(apps, None)

        for booking in (first, second):
            booking.refresh_from_db()
            self.assertEqual(booking.items[0]["kind"], "service")
            self.assertTrue(all(isinstance(line["price"], str) for line in booking.items))
            self.assert_adds_up(booking, booking.items)
