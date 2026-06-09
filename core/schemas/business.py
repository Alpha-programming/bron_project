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

    owner_id: int
    owner_username: str

    name: str
    description: str | None

    logo: str | None

    category: str

    address: str
    phone: str

    latitude: float | None
    longitude: float | None

    created_at: str