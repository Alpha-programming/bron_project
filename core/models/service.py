from django.db import models
from .business import Business


class Service(models.Model):

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="services"
    )

    title = models.CharField(max_length=255)

    description = models.TextField()

    category = models.CharField(max_length=100)

    image = models.ImageField(
        upload_to="services/",
        null=True,
        blank=True
    )

    duration = models.PositiveIntegerField(
        help_text="minutes"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title