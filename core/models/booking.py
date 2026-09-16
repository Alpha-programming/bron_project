from django.db import models

from .user import User
from .service import Service
from .business import Business
from .branch import Branch
from .staff import Staff


class Booking(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("rejected", "Rejected"),
    )

    ATTENDANCE_STATUS_CHOICES = (
        ("not_set", "Not Set"),
        ("visited", "Visited"),
        ("late", "Late"),
        ("no_show", "No Show"),
    )



    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE
    )

    booking_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings"
    )

    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    attendance_status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS_CHOICES,
        default="not_set"
    )

    extra_wait_minutes = models.PositiveSmallIntegerField(
        default=0
    )

    attendance_updated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    guest_count = models.PositiveIntegerField(
        default=1
    )
    products = models.ManyToManyField(
        "Product",
        blank=True,
        related_name="bookings"
    )

    notes = models.TextField(
        blank=True
    )

    cancel_reason = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.service}"