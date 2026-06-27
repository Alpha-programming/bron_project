from ninja import Schema
from decimal import Decimal
from typing import Optional


class ServiceCreateSchema(Schema):

    business_id: int

    title: str
    description: str
    category: str

    duration: int
    price: Decimal


class ServiceUpdateSchema(Schema):

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None

    duration: Optional[int] = None
    price: Optional[Decimal] = None

    is_active: Optional[bool] = None


class ServiceListSchema(Schema):

    id: int

    title: str
    category: str

    duration: int
    price: Decimal
    image: Optional[str]

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None


class ServiceOutSchema(Schema):

    id: int

    business_id: int

    title: str
    description: str

    category: str

    duration: int
    price: float

    is_active: bool
    image: Optional[str] = None

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None