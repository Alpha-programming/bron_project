from ninja import Schema

from core.utils.helpers import absolute_media_url


class CategoryShortSchema(Schema):

    id: int
    name: str
    slug: str


class CategoryOutSchema(Schema):

    id: int
    name: str
    slug: str
    icon: str | None = None
    business_count: int = 0

    @staticmethod
    def resolve_icon(obj, context):
        return absolute_media_url(context["request"], obj.icon)
