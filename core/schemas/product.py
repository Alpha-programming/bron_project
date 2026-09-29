from ninja import Schema
from pydantic import Field
from typing import Optional
from decimal import Decimal

from core.utils.helpers import absolute_media_url

IMAGE_DESCRIPTION = (
    "Absolute URL of the product photo, null if none. "
    "Upload via POST /api/products/{product_id}/image, remove via DELETE."
)


class ProductCreateSchema(Schema):
    business_id: int
    name: str
    description: Optional[str] = None
    price: Decimal


class ProductUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductOutSchema(Schema):
    id: int = Field(..., description="Product ID")
    business_id: int = Field(..., description="ID of the business selling the product")
    name: str = Field(..., description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    image: Optional[str] = Field(None, description=IMAGE_DESCRIPTION)
    price: float = Field(..., description="Current price")
    is_active: bool = Field(..., description="Inactive products are hidden from public lists")

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)


class ProductListSchema(Schema):
    id: int = Field(..., description="Product ID")
    name: str = Field(..., description="Product name")
    price: float = Field(..., description="Current price")
    image: Optional[str] = Field(None, description=IMAGE_DESCRIPTION)

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)
