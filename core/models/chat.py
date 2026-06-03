from django.db import models
from .user import User
from .business import Business


class Chat(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chats"
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="chats"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.business}"