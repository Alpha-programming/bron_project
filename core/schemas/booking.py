from ninja import Schema
from datetime import date, time
from typing import Optional, List

class BookingCreateSchema(Schema):
    business_id: int
    service_id: int
    branch_id: int
    staff_id: Optional[int] = None
    booking_date: date
    start_time: str  # Kept as str to allow safe manual conversion inside services
    end_time: str    # Kept as str to allow safe manual conversion inside services
    guest_count: int = 1
    product_ids: List[int] = []

class BookingUpdateSchema(Schema):
    status: Optional[str] = None
    staff_id: Optional[int] = None

class BookingOutSchema(Schema):
    id: int
    user_id: int
    business_id: int
    service_id: int
    branch_id: int
    staff_id: Optional[int] = None
    booking_date: date
    start_time: time
    end_time: time
    guest_count: int
    total_price: float
    status: str

class BookingListSchema(Schema):
    id: int
    booking_date: date
    start_time: time
    status: str
    total_price: float