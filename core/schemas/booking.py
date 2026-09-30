import math
from datetime import time
# Aliased because AvailableSlotsOutSchema has a field called `date`
from datetime import date, date as date_type
from decimal import Decimal
from typing import List, Literal, Optional

from ninja import Schema
from pydantic import Field

from core.utils.helpers import absolute_media_url

ItemKind = Literal["service", "product"]

MAX_ITEM_QUANTITY = 100


def _is_int(value):
    # bool is an int subclass, but True is not an id or a quantity
    return isinstance(value, int) and not isinstance(value, bool)


def _snapshot_price(value):
    try:
        price = float(value)
    except (TypeError, ValueError):
        return 0.0
    # NaN/Infinity would produce invalid JSON
    return price if math.isfinite(price) else 0.0


def snapshot_items(booking):
    """
    Booking.items as stored (prices are decimal strings) -> output rows with
    float prices.

    The JSON can be edited outside the API (admin, shell), so one malformed
    value must not break every list that contains the booking: rows without
    an int id or a known kind are skipped, a bad price becomes 0.0, a bad
    quantity 1 and a missing name "".
    """
    items = booking.items
    if not isinstance(items, list):
        return []

    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _is_int(item.get("id")) or item.get("kind") not in ("service", "product"):
            continue

        quantity = item.get("quantity")
        name = item.get("name")

        rows.append({
            "id": item["id"],
            "name": name if isinstance(name, str) else "",
            "price": _snapshot_price(item.get("price")),
            "quantity": quantity if _is_int(quantity) and quantity >= 1 else 1,
            "kind": item["kind"],
        })

    return rows


class BookingItemInSchema(Schema):
    id: int = Field(..., description="Service or product id, depending on kind")
    kind: ItemKind = Field(..., description='"service" or "product"')
    quantity: int = Field(
        1,
        ge=1,
        le=MAX_ITEM_QUANTITY,
        description=f"Units ordered, 1-{MAX_ITEM_QUANTITY}. Duplicate lines are merged "
                    f"and the merged quantity may not exceed {MAX_ITEM_QUANTITY} either.",
    )
    name: Optional[str] = Field(
        None,
        description="Ignored. The server always uses the current name from the database.",
    )
    price: Optional[Decimal] = Field(
        None,
        description="Ignored. The server always charges the current price from the database.",
    )


class BookingItemSchema(Schema):
    id: int = Field(..., description="Service or product id")
    name: str = Field(..., description="Service title or product name at booking time")
    price: float = Field(..., description="Unit price charged at booking time")
    quantity: int = Field(..., description="Units ordered")
    kind: ItemKind = Field(..., description='"service" or "product"')


class BookingCreateSchema(Schema):
    business_id: int
    service_id: int = Field(..., description="Booked service; always part of the order")
    branch_id: int
    staff_id: Optional[int] = Field(
        None,
        description="Optional staff member of the business. Must be free at this time: "
                    "a pending/confirmed booking of this staff member in any service that "
                    "overlaps it gives 400 \"Selected time is not available: staff member "
                    "is busy\".",
    )
    booking_date: date = Field(..., description="YYYY-MM-DD")
    # Kept as str to allow safe manual conversion inside services
    start_time: str = Field(
        ...,
        description="HH:MM. For a service with its own schedule it must be one of "
                    "the times listed for booking_date.",
    )
    end_time: str = Field(
        ...,
        description="HH:MM, after start_time. For a service with its own schedule "
                    "it must equal start_time + service duration.",
    )
    guest_count: int = 1
    items: List[BookingItemInSchema] = Field(
        [],
        description="Order composition. Every item must be an active service or product "
                    "of the same business. The booked service is added with quantity 1 "
                    "if missing. total_price is calculated on the server from current prices.",
    )
    product_ids: List[int] = Field(
        [],
        description="Deprecated, use items. Products of the business added once each; "
                    "unknown ids are skipped. Ignored when items is sent.",
    )


class BookingRescheduleSchema(Schema):
    booking_date: date = Field(..., description="YYYY-MM-DD")
    start_time: str = Field(
        ...,
        description="HH:MM. For a service with its own schedule it must be one of "
                    "the times listed for booking_date.",
    )
    end_time: str = Field(
        ...,
        description="HH:MM, after start_time. For a service with its own schedule "
                    "it must equal start_time + service duration.",
    )


class BookingUpdateSchema(Schema):
    # Status changes go through /approve, /reject and /cancel only
    staff_id: Optional[int] = Field(
        None,
        description="Staff member of the same business to assign. Must be free at the "
                    "booking time: a pending/confirmed booking of this staff member in any "
                    "service that overlaps it gives 409. Omit or null to keep the current one.",
    )


class BookingUserSchema(Schema):
    """Customer shown to the business. No phone or email on purpose."""

    first_name: str
    last_name: str
    full_name: str = Field(
        ..., description="First and last name, empty string when neither is set"
    )
    username: str = Field(..., description="Fallback for display when full_name is empty")
    avatar: Optional[str] = Field(..., description="Absolute URL of the avatar, null if none")

    @staticmethod
    def resolve_full_name(obj):
        return obj.get_full_name()

    @staticmethod
    def resolve_avatar(obj, context):
        return absolute_media_url(context["request"], obj.avatar)


class BookingOutSchema(Schema):
    id: int
    user_id: int
    user: BookingUserSchema = Field(..., description="Customer who made the booking")
    business_id: int
    service_id: int
    branch_id: int
    staff_id: Optional[int] = None
    booking_date: date
    start_time: time
    end_time: time
    guest_count: int
    total_price: float = Field(..., description="Sum of price x quantity over items")
    status: str
    attendance_status: str
    extra_wait_minutes: int
    items: List[BookingItemSchema] = Field(
        ..., description="Order composition with the prices charged at booking time"
    )

    @staticmethod
    def resolve_items(obj):
        return snapshot_items(obj)


class BookingListSchema(Schema):
    id: int
    booking_date: date
    start_time: time
    status: str
    total_price: float = Field(..., description="Sum of price x quantity over items")
    items: List[BookingItemSchema] = Field(
        ..., description="Order composition with the prices charged at booking time"
    )

    @staticmethod
    def resolve_items(obj):
        return snapshot_items(obj)


AttendanceStatus = Literal["visited", "late", "no_show"]


class BookingAttendanceSchema(Schema):
    status: AttendanceStatus = Field(
        ...,
        description="visited - came on time, late - came late, no_show - did not come",
    )
    extra_wait_minutes: int = Field(
        0,
        description="Only for late: how long the business waited, 0-10 minutes. Ignored otherwise.",
    )


class AvailableSlotSchema(Schema):
    start_time: str = Field(..., description="Slot start, HH:MM")
    end_time: str = Field(..., description="Slot end, HH:MM")
    is_available: bool = Field(..., description="True while at least one place is free")
    available_spots: int = Field(
        ...,
        description="Free places: service capacity minus guests of all pending/confirmed "
                    "bookings of the service; 0 when the requested staff member is busy",
    )


class AvailableSlotsOutSchema(Schema):
    business_id: int
    service_id: int
    branch_id: int
    staff_id: Optional[int] = Field(
        None,
        description="Staff member whose own bookings (in any service) were also checked; "
                    "null = no staff member requested",
    )
    date: date_type = Field(..., description="Requested day, YYYY-MM-DD")
    duration: int = Field(..., description="Service duration in minutes (slot length)")
    capacity: int = Field(..., description="Guests per slot")
    slots: List[AvailableSlotSchema] = Field(
        ...,
        description="Slots from the service schedule if it has one, otherwise from the "
                    "business working hours. Empty on blocked or closed days, past dates "
                    "and for businesses that are not approved yet.",
    )
