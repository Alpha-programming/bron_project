from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from .user import User
from .business import Business


class Review(models.Model):

    REVIEW_TYPE_CHOICES = (
        ("business", "Business Review"),
        ("customer", "Customer Review"),
    )

    # Author of review
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="written_reviews"
    )

    # Customer -> Business
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reviews"
    )

    # Business -> Customer
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="received_reviews"
    )

    booking = models.ForeignKey(
        "Booking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reviews"
    )

    review_type = models.CharField(
        max_length=20,
        choices=REVIEW_TYPE_CHOICES,
        default="business"
    )

    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )

    comment = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "review_type"],
                name="unique_review_type_per_booking"
            )
        ]

    def __str__(self):
        if self.review_type == "customer":
            return f"{self.customer} - {self.rating}"

        return f"{self.business} - {self.rating}"