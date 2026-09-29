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


# bookingReminder is camelCase on purpose: the mobile app uses these exact keys,
# so the field is named that way instead of relying on aliases.
class NotificationSettingsSchema(Schema):
    push: bool = Field(..., description="Push notifications in the app")
    email: bool = Field(..., description="Email notifications")
    bookingReminder: bool = Field(..., description="Reminders before a booking")
    promotions: bool = Field(..., description="News and promotional offers")


class NotificationSettingsUpdateSchema(Schema):
    push: bool | None = Field(
        None, description="Push notifications in the app; omit or null to keep the current value"
    )
    email: bool | None = Field(
        None, description="Email notifications; omit or null to keep the current value"
    )
    bookingReminder: bool | None = Field(
        None, description="Reminders before a booking; omit or null to keep the current value"
    )
    promotions: bool | None = Field(
        None, description="News and promotional offers; omit or null to keep the current value"
    )