from ninja import Schema


class BookingCreateSchema(Schema):

    business_id: int
    service_id: int
    branch_id: int

    staff_id: int | None = None

    booking_date: str

    start_time: str
    end_time: str

    guest_count: int = 1

    product_ids: list[int] = []


class BookingUpdateSchema(Schema):

    status: str | None = None

    staff_id: int | None = None


class BookingOutSchema(Schema):

    id: int

    user_id: int

    business_id: int
    service_id: int

    branch_id: int

    staff_id: int | None = None

    booking_date: str

    start_time: str
    end_time: str

    guest_count: int

    total_price: float

    status: str


class BookingListSchema(Schema):

    id: int

    booking_date: str

    start_time: str

    status: str

    total_price: float