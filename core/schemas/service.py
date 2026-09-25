from ninja import Schema
from pydantic import Field
from decimal import Decimal
from datetime import date
from typing import List, Optional

from core.utils.helpers import absolute_media_url


class ServiceCreateSchema(Schema):

    business_id: int

    title: str
    description: str
    category: str

    duration: int = Field(..., ge=1)
    price: Decimal
    capacity: int = Field(1, ge=1, le=1000)


class ServiceUpdateSchema(Schema):

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None

    duration: Optional[int] = Field(None, ge=1)
    price: Optional[Decimal] = None
    capacity: Optional[int] = Field(None, ge=1, le=1000)

    is_active: Optional[bool] = None


class ServiceListSchema(Schema):

    id: int

    title: str
    category: str

    duration: int
    price: Decimal
    capacity: int
    image: Optional[str]

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)


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

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)


class ServiceSlotSchema(Schema):

    start_time: str
    end_time: str
    available_spots: int
    is_available: bool


class ServiceAvailabilityOutSchema(Schema):

    service_id: int
    date: date
    duration: int
    capacity: int
    slots: List[ServiceSlotSchema]


class ServiceAvailableDateSchema(Schema):

    date: date
    free_slots: int