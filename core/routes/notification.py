from typing import List

from ninja import Router
from ninja.pagination import paginate, LimitOffsetPagination

from core.security import JWTAuth
from core.schemas.notification import (
    NotificationOutSchema,
    UnreadCountSchema,
    ReadAllSchema,
)
from core.services.notification import (
    get_user_notifications,
    get_unread_count,
    mark_read,
    mark_all_read,
    delete_notification,
)

router = Router(tags=["Notifications"], auth=JWTAuth())


@router.get("/", response=List[NotificationOutSchema])
@paginate(LimitOffsetPagination)
def notification_list(request, unread_only: bool = False):
    """
    Current user's notifications, newest first. Supports ?limit=&offset=.
    """
    return get_user_notifications(request.auth, unread_only)


@router.get("/unread-count", response=UnreadCountSchema)
def unread_count(request):
    return {"count": get_unread_count(request.auth)}


# Static path must be declared before /{notification_id}/...
@router.patch("/read-all", response=ReadAllSchema)
def read_all(request):
    return {"updated": mark_all_read(request.auth)}


@router.patch("/{notification_id}/read", response=NotificationOutSchema)
def read_one(request, notification_id: int):
    return mark_read(request.auth, notification_id)


@router.delete("/{notification_id}")
def delete_one(request, notification_id: int):
    return delete_notification(request.auth, notification_id)
