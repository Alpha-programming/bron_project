from django.db import models

from .user import User
from .business import Business
from django.core.validators import MaxValueValidator

from django.core.validators import MinValueValidator


class Review(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE
    )

    rating = models.PositiveSmallIntegerField(

        validators=[

            MinValueValidator(1),

            MaxValueValidator(5)

        ]

    )

    comment = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.business} - {self.rating}"