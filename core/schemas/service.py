from ninja import Schema
from pydantic import Field, field_validator
from decimal import Decimal
# Aliased: pydantic breaks on a field named `date` annotated as `date` once it has a default/Field
from datetime import date as date_type
from typing import List, Optional

from core.utils.helpers import absolute_media_url
from core.utils.schedule import normalize_availability


AVAILABILITY_DESCRIPTION = (
    "Own schedule of the service: the exact dates and start times it can be booked at. "
    "Each time starts a slot lasting `duration` minutes; a slot may not end after 23:59. "
    "An empty list means the service has no own schedule and is bookable within the "
    "business working hours. When the list is not empty, working hours are ignored and "
    "the service can be booked only at the listed dates and times; a date listed with "
    "empty `times` is a day off, dates not listed are unavailable. Blocked dates still "
    "close the day. Dates must be unique; times are de-duplicated and sorted."
)

# Shared by /api/services/{id}/availability, /available-dates and
# /api/bookings/available-slots, which apply the same rule
SLOT_STAFF_DESCRIPTION = (
    "Optional staff member of the same business. Free places are always counted over "
    "all pending/confirmed bookings of the service, whoever the staff member is. "
    "With staff_id, a slot that overlaps a pending/confirmed booking of this staff "
    "member in any service is also unavailable (is_available false, available_spots 0), "
    "so every slot shown as available can be booked with this staff member."
)


class ServiceScheduleDaySchema(Schema):
    """One day of a service schedule."""

    date: date_type = Field(
        ...,
        description="Calendar date, YYYY-MM-DD",
        examples=["2026-10-01"],
    )
    times: List[str] = Field(
        ...,
        description="Slot start times on this date, HH:MM (24h). Empty list = day off.",
        examples=[["10:00", "14:30"]],
    )


def _validate_availability(value):
    # ValueError from here becomes a 422 validation error.
    # The duration-dependent check (slot ends after 23:59) runs in the service
    # layer, which knows the effective duration.
    return normalize_availability(value)


class ServiceCreateSchema(Schema):

    business_id: int

    title: str
    description: str
    category: str

    duration: int = Field(..., ge=1, description="Slot length in minutes")
    price: Decimal
    capacity: int = Field(1, ge=1, le=1000)

    availability: List[ServiceScheduleDaySchema] = Field(
        default_factory=list,
        description=AVAILABILITY_DESCRIPTION + " Omit or send [] to follow working hours.",
    )

    @field_validator("availability", mode="before")
    @classmethod
    def normalize_availability_field(cls, value):
        return _validate_availability(value)


class ServiceUpdateSchema(Schema):

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None

    duration: Optional[int] = Field(None, ge=1, description="Slot length in minutes")
    price: Optional[Decimal] = None
    capacity: Optional[int] = Field(None, ge=1, le=1000)

    is_active: Optional[bool] = None

    availability: Optional[List[ServiceScheduleDaySchema]] = Field(
        None,
        description=AVAILABILITY_DESCRIPTION
        + " Omit the field to keep the current schedule; a sent list replaces it "
          "completely; null or [] removes it (back to working hours).",
    )

    @field_validator("availability", mode="before")
    @classmethod
    def normalize_availability_field(cls, value):
        return _validate_availability(value)


class ServiceListSchema(Schema):

    id: int

    title: str
    category: str

    duration: int
    price: Decimal
    capacity: int
    image: Optional[str]

    availability: List[ServiceScheduleDaySchema] = Field(
        ...,
        description=AVAILABILITY_DESCRIPTION,
    )

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)

    @staticmethod
    def resolve_availability(obj):
        return obj.availability or []


class ServiceOutSchema(Schema):

    id: int

    business_id: int

    title: str
    description: str

    category: str

    duration: int
    price: float
    capacity: int

    is_active: bool
    image: Optional[str] = None

    availability: List[ServiceScheduleDaySchema] = Field(
        ...,
        description=AVAILABILITY_DESCRIPTION,
    )

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)

    @staticmethod
    def resolve_availability(obj):
        return obj.availability or []


class ServiceSlotSchema(Schema):

    start_time: str = Field(..., description="Slot start, HH:MM")
    end_time: str = Field(..., description="Slot end, HH:MM (start + service duration)")
    available_spots: int = Field(
        ...,
        description="Guests that can still be booked into this slot: capacity minus guests "
                    "of all pending/confirmed bookings of the service overlapping it; "
                    "0 when the requested staff member is busy",
    )
    is_available: bool = Field(..., description="True when available_spots > 0")


class ServiceAvailabilityOutSchema(Schema):

    service_id: int
    date: date_type
    duration: int = Field(..., description="Slot length in minutes")
    capacity: int = Field(..., description="Guests per slot")
    slots: List[ServiceSlotSchema] = Field(
        ...,
        description="Bookable slots of the day in start order; already started slots "
                    "and past dates are never listed",
    )


class ServiceAvailableDateSchema(Schema):

    date: date_type
    free_slots: int = Field(..., description="Number of slots with at least one free place")
