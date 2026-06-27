from datetime import date
from ninja import Schema

class BlockedDateCreateSchema(Schema):
    business_id: int
    date: date
    reason: str | None = None

class BlockedDateUpdateSchema(Schema):
    reason: str | None = None

class BlockedDateOutSchema(Schema):
    id: int
    business_id: int
    date: date
    reason: str | None = None

class BlockedCheckOutSchema(Schema):
    business_id: int
    date: date
    is_blocked: bool
    reason: str | None = None