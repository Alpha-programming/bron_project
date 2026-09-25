from ninja import Schema

from core.utils.helpers import absolute_media_url


class BusinessLogoOutSchema(Schema):

    id: int

    logo: str | None

    @staticmethod
    def resolve_logo(obj, context):
        return absolute_media_url(context["request"], obj.logo)
