from ninja import Schema


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