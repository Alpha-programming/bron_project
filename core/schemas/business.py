from ninja import Schema
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from pydantic import Field, field_validator
from typing import Optional

from core.schemas.category import CategoryShortSchema
from core.utils.helpers import absolute_media_url


class SocialLinksSchema(Schema):
    """
    Fixed set of social profiles. Empty strings are treated as "not set";
    anything else must be a full http(s) URL.
    """

    instagram: Optional[str] = None
    telegram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def validate_url(cls, value, info):
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError(f"{info.field_name} must be a full URL starting with http:// or https://")
        return value


def _check_email(value):
    """Reuse Django's EmailField validation so API and admin agree."""
    if value is None:
        return None
    value = value.strip()
    try:
        validate_email(value)
    except ValidationError:
        raise ValueError("Enter a valid email address")
    return value


class BusinessCreateSchema(Schema):

    name: str
    description: str = ""

    category_id: int

    address: str
    phone: str
    email: str
    owner_name: str = Field(..., min_length=1, max_length=150)

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value):
        return _check_email(value)

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    tin: str = ""
    website: str = ""

    social_links: SocialLinksSchema = SocialLinksSchema()

    comments: str = ""


class BusinessUpdateSchema(Schema):

    name: Optional[str] = None
    description: Optional[str] = None

    category_id: Optional[int] = None

    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=150)

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value):
        return _check_email(value)

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    tin: Optional[str] = None
    website: Optional[str] = None
    social_links: Optional[SocialLinksSchema] = None
    comments: Optional[str] = None


class BusinessListSchema(Schema):

    id: int

    name: str
    category: CategoryShortSchema

    address: str
    phone: str

    logo: str | None

    views_count: int

    @staticmethod
    def resolve_logo(obj, context):
        return absolute_media_url(context["request"], obj.logo)


class BusinessOutSchema(Schema):

    id: int

    owner_id: int
    owner_username: str

    name: str
    description: str | None

    logo: str | None

    category: CategoryShortSchema

    address: str
    phone: str
    email: str
    owner_name: str

    latitude: float | None = None
    longitude: float | None = None

    tin: str | None = None
    website: str | None = None
    social_links: SocialLinksSchema
    comments: str | None = None

    views_count: int

    created_at: str

    @staticmethod
    def resolve_social_links(obj):
        # Always return every key so the frontend gets null for unset networks
        return SocialLinksSchema(**(obj.social_links or {}))

    @staticmethod
    def resolve_logo(obj, context):
        return absolute_media_url(context["request"], obj.logo)

    @staticmethod
    def resolve_owner_id(obj):
        return obj.owner.id

    @staticmethod
    def resolve_owner_username(obj):
        return obj.owner.username

    @staticmethod
    def resolve_created_at(obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")


class BusinessStatsOutSchema(Schema):

    total_bookings: int
    pending_bookings: int
    approved_bookings: int
    cancelled_bookings: int
    total_revenue: str
    views_count: int


class BusinessViewOutSchema(Schema):

    counted: bool
    views_count: int