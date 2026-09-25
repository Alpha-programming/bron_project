from ninja import Schema
from pydantic import Field

from core.utils.helpers import absolute_media_url

class PhoneTgSchema(Schema):
    phone: str

class UserProfileOutSchema(Schema):

    id: int
    username: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    telegram_id: int | None = None
    avatar: str | None = None
    role: str
    language: str
    is_verified: bool
    rating: float
    reviews_count: int

    @staticmethod
    def resolve_full_name(obj):
        return obj.get_full_name()

    @staticmethod
    def resolve_avatar(obj, context):
        return absolute_media_url(context["request"], obj.avatar)

class UserProfileUpdateSchema(Schema):

    first_name: str | None = Field(None, max_length=150)
    last_name: str | None = Field(None, max_length=150)
    email: str | None = None
    phone: str | None = None
    language: str | None = None
    telegram_id: int | None = None

class ChangePasswordSchema(Schema):
    old_password: str
    new_password: str