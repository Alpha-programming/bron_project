from django.db import models

from .business import Business
from .user import User


class BusinessView(models.Model):
    """
    Log of business page views, one row per counted request.
    Business.views_count holds the running total.
    """

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="views"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_views"
    )

    ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["business", "user", "viewed_at"]),
            models.Index(fields=["business", "ip", "viewed_at"]),
        ]

    def __str__(self):
        return f"{self.business_id} viewed by {self.user_id or self.ip}"
