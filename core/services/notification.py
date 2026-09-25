from ninja.errors import HttpError

from core.models import Notification


def notify(user, notification_type, title, message, booking=None):
    """
    Single entry point for creating notifications.
    """
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        booking=booking,
    )


def get_user_notifications(user, unread_only=False):
    qs = Notification.objects.filter(user=user)
    if unread_only:
        qs = qs.filter(is_read=False)
    return qs


def get_unread_count(user):
    return Notification.objects.filter(user=user, is_read=False).count()


def _get_own_notification(user, notification_id):
    try:
        # Filtering by user keeps other users' ids indistinguishable from missing ones
        return Notification.objects.get(id=notification_id, user=user)
    except Notification.DoesNotExist:
        raise HttpError(404, "Notification not found")


def mark_read(user, notification_id):
    notification = _get_own_notification(user, notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return notification


def mark_all_read(user):
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


def delete_notification(user, notification_id):
    notification = _get_own_notification(user, notification_id)
    notification.delete()
    return {"message": "Notification deleted successfully"}
