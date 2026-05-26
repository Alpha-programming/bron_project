from django.db import models

from core.models.user import User


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

    category = models.CharField(max_length=100)

    address = models.CharField(max_length=255)

    latitude = models.FloatField(
        null=True,
        blank=True
    )

    longitude = models.FloatField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Business"
        verbose_name_plural = "Businesses"
        ordering = ["-created_at"]