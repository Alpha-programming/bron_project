from datetime import datetime

from ninja import Schema


class NotificationOutSchema(Schema):

    id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    booking_id: int | None = None
    created_at: datetime


class UnreadCountSchema(Schema):

    count: int


class ReadAllSchema(Schema):

    updated: int
