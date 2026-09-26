from django.db import models

from .user import User


class Notification(models.Model):

    TYPE_CHOICES = (
        ("booking_created", "Booking created"),
        ("booking_confirmed", "Booking confirmed"),
        ("booking_rejected", "Booking rejected"),
        ("booking_cancelled", "Booking cancelled"),
        ("booking_rescheduled", "Booking rescheduled"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default="booking_created"
    )

    booking = models.ForeignKey(
        "Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications"
    )

    title = models.CharField(max_length=255)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return self.title
