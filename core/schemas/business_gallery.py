from ninja import Schema
from pydantic import Field

from core.utils.helpers import absolute_media_url


class BusinessGalleryOutSchema(Schema):

    id: int

    business_id: int

    image: str = Field(
        ...,
        description="Absolute URL of the picture",
    )

    sort_order: int = Field(
        ...,
        description="Display position: lower comes first, ties go by id",
    )

    created_at: str = Field(
        ...,
        description="Upload time, YYYY-MM-DD HH:MM:SS",
    )

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)

    @staticmethod
    def resolve_created_at(obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")


class BusinessGalleryDeleteSchema(Schema):

    message: str
