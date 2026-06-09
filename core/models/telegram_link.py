from django.db import models
from .user import User


class TelegramLinkToken(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    token = models.CharField(
        max_length=255,
        unique=True
    )

    is_used = models.BooleanField(
        default=False
    )

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.user.username