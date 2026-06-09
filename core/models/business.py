from django.db import models
from .user import User


class Business(models.Model):

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="businesses"
    )

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    logo = models.ImageField(
        upload_to="business_logos/",
        null=True,
        blank=True
    )

    CATEGORY_CHOICES = (
        ("gym", "Gym"),
        ("spa", "Spa"),
        ("salon", "Salon"),
        ("clinic", "Clinic"),
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES
    )

    address = models.CharField(max_length=255)

    phone = models.CharField(max_length=20)

    latitude = models.FloatField(
        null=True,
        blank=True
    )

    longitude = models.FloatField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name