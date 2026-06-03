from django.db import models
from .business import Business


class WorkingHours(models.Model):

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE
    )

    day_of_week = models.IntegerField()

    open_time = models.TimeField()

    close_time = models.TimeField()

    is_closed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.business} - {self.day_of_week}"