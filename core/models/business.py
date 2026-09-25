from django.db import models
from .user import User
from .category import Category


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

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="businesses"
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

    tin = models.CharField(
        max_length=30,
        blank=True
    )

    website = models.URLField(
        blank=True
    )

    social_links = models.JSONField(
        default=dict,
        blank=True
    )

    comments = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name