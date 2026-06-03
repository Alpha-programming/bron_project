from ninja import Schema


class UserProfileOutSchema(Schema):

    id: int
    username: str
    email: str
    phone: str
    telegram_id: int | None = None
    role: str
    language: str
    is_verified: bool


class UserProfileUpdateSchema(Schema):

    email: str | None = None
    phone: str | None = None
    language: str | None = None
    telegram_id: int | None = None