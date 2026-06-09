from django.db import models
from .business import Business


class Product(models.Model):

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="products"
    )

    name = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True
    )

    image = models.ImageField(
        upload_to="products/",
        null=True,
        blank=True
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name