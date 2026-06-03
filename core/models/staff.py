from django.db import models
from .business import Business


class Staff(models.Model):

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="staff"
    )

    full_name = models.CharField(max_length=255)

    position = models.CharField(max_length=100)

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name