from ninja import Schema


class BlockedDateCreateSchema(Schema):

    business_id: int

    date: str

    reason: str | None = None


class BlockedDateUpdateSchema(Schema):

    reason: str | None = None


class BlockedDateOutSchema(Schema):

    id: int

    business_id: int

    date: str

    reason: str | None = None