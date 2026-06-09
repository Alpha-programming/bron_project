from django.db import models

from .booking import Booking


class Payment(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    PAYMENT_METHODS = (
        ("cash", "Cash"),
        ("card", "Card"),
        ("stripe", "Stripe"),
        ("payme", "Payme"),
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )

    transaction_id = models.CharField(
        max_length=255,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.id)