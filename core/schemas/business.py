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


class BusinessUpdateSchema(Schema):

    name: Optional[str] = None
    description: Optional[str] = None

    category: Optional[str] = None

    address: Optional[str] = None
    phone: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BusinessListSchema(Schema):

    id: int

    name: str
    category: str

    address: str
    phone: str

    logo: str | None


class BusinessOutSchema(Schema):
    id: int

    # We keep these fields exactly as they are
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
    created_at: str

    # FIX: Add explicit resolvers so Ninja knows exactly how to map from the 'owner' relation
    @staticmethod
    def resolve_owner_id(obj):
        return obj.owner.id

    @staticmethod
    def resolve_owner_username(obj):
        return obj.owner.username

    @staticmethod
    def resolve_created_at(obj):
        # Converts datetime to clean string representation if needed
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(obj.created_at, 'strftime') else str(
            obj.created_at)

class BusinessStatsOutSchema(Schema):
    total_bookings: int
    pending_bookings: int
    approved_bookings: int
    cancelled_bookings: int
    total_revenue: str