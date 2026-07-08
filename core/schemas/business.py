from ninja import Schema
from typing import Optional


class BusinessCreateSchema(Schema):

    name: str
    description: Optional[str] = None

    category: str

    address: str
    phone: str

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    tin: Optional[str] = None
    website: Optional[str] = None
    social_links: dict = {}
    comments: Optional[str] = None


class BusinessUpdateSchema(Schema):

    name: Optional[str] = None
    description: Optional[str] = None

    category: Optional[str] = None

    address: Optional[str] = None
    phone: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    tin: Optional[str] = None
    website: Optional[str] = None
    social_links: Optional[dict] = None
    comments: Optional[str] = None


class BusinessListSchema(Schema):

    id: int

    name: str
    category: str

    address: str
    phone: str

    logo: str | None


class BusinessOutSchema(Schema):

    id: int

    owner_id: int
    owner_username: str

    name: str
    description: str | None

    logo: str | None

    category: str

    address: str
    phone: str

    latitude: float | None = None
    longitude: float | None = None

    tin: str | None = None
    website: str | None = None
    social_links: dict
    comments: str | None = None

    created_at: str

    @staticmethod
    def resolve_owner_id(obj):
        return obj.owner.id

    @staticmethod
    def resolve_owner_username(obj):
        return obj.owner.username

    @staticmethod
    def resolve_created_at(obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")


class BusinessStatsOutSchema(Schema):

    total_bookings: int
    pending_bookings: int
    approved_bookings: int
    cancelled_bookings: int
    total_revenue: str