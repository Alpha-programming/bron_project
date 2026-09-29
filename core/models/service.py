from django.core.exceptions import ValidationError
from django.db import models

from core.utils.schedule import normalize_availability
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

    # How many guests can be booked into the same time slot
    capacity = models.PositiveIntegerField(
        default=1,
        help_text="guests per time slot"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # Own schedule, see core.utils.schedule. Empty = follow working hours.
    availability = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"date": "YYYY-MM-DD", "times": ["HH:MM", ...]}]. '
                  "Empty list = bookable within the business working hours."
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def clean(self):
        super().clean()
        # PositiveIntegerField accepts 0, but a zero-length slot is meaningless
        if self.duration is not None and self.duration < 1:
            raise ValidationError({"duration": "Duration must be at least 1 minute"})
        try:
            self.availability = normalize_availability(self.availability, self.duration)
        except ValueError as exc:
            raise ValidationError({"availability": str(exc)})

    def __str__(self):
        return self.title