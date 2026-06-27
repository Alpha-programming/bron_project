from ninja import Schema
from typing import Optional
from decimal import Decimal

class ProductCreateSchema(Schema):
    business_id: int
    name: str
    description: Optional[str] = None
    price: Decimal

class ProductUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal]= None
    is_active: Optional[bool] = None

class ProductOutSchema(Schema):
    id: int
    business_id: int
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    price: float
    is_active: bool

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None

class ProductListSchema(Schema):
    id: int
    name: str
    price: float
    image: Optional[str] = None

    @staticmethod
    def resolve_image(obj):
        return obj.image.url if obj.image else None