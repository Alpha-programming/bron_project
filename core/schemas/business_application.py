import re
from datetime import datetime
from typing import Optional

from ninja import Schema
from pydantic import ConfigDict, Field, field_validator

from core.schemas.business import _check_email

# Optional "+" and 7-15 digits once spaces, dashes, dots and brackets are removed
PHONE_RE = re.compile(r"\+?[0-9]{7,15}")


class BusinessApplicationCreateSchema(Schema):

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(..., min_length=1, max_length=150)
    phone: str

    # Optional fields: omitted, null and "" all mean "not provided"
    email: Optional[str] = Field("", max_length=254)
    social: Optional[str] = Field("", max_length=255)
    comment: Optional[str] = Field("", max_length=120)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        value = re.sub(r"[\s().-]", "", value)
        if not PHONE_RE.fullmatch(value):
            raise ValueError("Enter a valid phone number")
        return value

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value):
        if not value:
            return ""
        return _check_email(value)

    @field_validator("social", "comment")
    @classmethod
    def none_to_blank(cls, value):
        return value or ""


class BusinessApplicationOutSchema(Schema):

    id: int
    full_name: str
    phone: str
    email: str
    social: str
    comment: str
    status: str
    created_at: datetime
