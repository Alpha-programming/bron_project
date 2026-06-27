from ninja import Schema
from typing import List, Optional
from core.schemas.booking import BookingOutSchema
from core.schemas.working_hours import WorkingHoursOutSchema

class StaffCreateSchema(Schema):
    business_id: int
    full_name: str
    position: str
    phone: str | None = None

class StaffUpdateSchema(Schema):
    full_name: str | None = None
    position: str | None = None
    phone: str | None = None
    is_active: bool | None = None

class StaffListSchema(Schema):
    id: int
    full_name: str
    position: str
    phone: str
    is_active: bool

class StaffOutSchema(Schema):
    id: int
    business_id: int
    full_name: str
    position: str
    phone: str
    is_active: bool

class StaffScheduleOutSchema(Schema):
    staff_id: int
    full_name: str
    working_hours: List[WorkingHoursOutSchema]