# Aliased: pydantic breaks on a field named `date` annotated as `date` once it has a default/Field
from datetime import date as date_type
from ninja import Schema
from pydantic import Field

class BlockedDateCreateSchema(Schema):
    business_id: int
    date: date_type
    reason: str | None = None

class BlockedDateUpdateSchema(Schema):
    reason: str | None = None

class BlockedDateOutSchema(Schema):
    id: int
    business_id: int
    date: date_type
    reason: str | None = None

class BlockedCheckOutSchema(Schema):
    business_id: int = Field(..., description="Business ID that was checked")
    date: date_type = Field(..., description="Checked date, YYYY-MM-DD")
    is_blocked: bool = Field(..., description="True when the business has blocked this date")
    # Required but nullable: the key is always present in the response
    reason: str | None = Field(
        ..., description="Reason set by the business; null when the date is not blocked or no reason was given"
    )
