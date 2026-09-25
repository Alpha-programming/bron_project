from ninja import Schema

from core.utils.helpers import absolute_media_url


class BusinessGalleryOutSchema(Schema):

    id: int

    business_id: int

    image: str

    created_at: str

    @staticmethod
    def resolve_image(obj, context):
        return absolute_media_url(context["request"], obj.image)

    @staticmethod
    def resolve_created_at(obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")


class BusinessGalleryDeleteSchema(Schema):

    message: str
