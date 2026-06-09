from ninja import Schema

from typing import Optional


class ServiceCreateSchema(Schema):

    business_id: int

    title: str
    description: str
    category: str

    duration: int
    price: float


class ServiceUpdateSchema(Schema):

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None

    duration: Optional[int] = None
    price: Optional[float] = None

    is_active: Optional[bool] = None


class ServiceListSchema(Schema):

    id: int

    title: str
    category: str

    duration: int
    price: float


class ServiceOutSchema(Schema):

    id: int

    business_id: int

    title: str
    description: str

    category: str

    duration: int
    price: float

    is_active: bool