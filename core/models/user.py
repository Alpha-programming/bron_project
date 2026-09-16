from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Avg

class User(AbstractUser):

    ROLE_CHOICES = (
        ("customer", "Customer"),
        ("business_owner", "Business Owner"),
        ("admin", "Admin"),
        ("staff", "Staff"),
    )

    email = models.EmailField(unique=True)

    phone = models.CharField(
        max_length=20,
        unique=True
    )

    telegram_id = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True
    )

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default="customer"
    )

    language = models.CharField(
        max_length=10,
        default="en"
    )

    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    REQUIRED_FIELDS = ["email"]

    @property
    def rating(self):
        result = self.received_reviews.filter(
            review_type="customer"
        ).aggregate(
            average=Avg("rating")
        )

        return round(result["average"] or 0, 1)

    @property
    def reviews_count(self):
        return self.received_reviews.filter(
            review_type="customer"
        ).count()

    def __str__(self):
        return self.username