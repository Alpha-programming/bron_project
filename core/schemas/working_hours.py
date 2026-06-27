from datetime import time
from typing import Optional
from ninja import Schema

class WorkingHoursCreateSchema(Schema):
    business_id: int
    day_of_week: int
    open_time: str
    close_time: str
    is_closed: bool = False

class WorkingHoursUpdateSchema(Schema):
    open_time: str | None = None
    close_time: str | None = None
    is_closed: bool | None = None

class WorkingHoursOutSchema(Schema):
    id: int
    business_id: int
    day_of_week: int
    open_time: time
    close_time: time
    is_closed: bool

class TodayScheduleOutSchema(Schema):
    business_id: int
    day_of_week: int
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool
    msg: str