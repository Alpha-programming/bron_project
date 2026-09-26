from django.db import models

from .user import User


class BusinessApplication(models.Model):
    """
    Request from the "Register your business" form: contact details only,
    no category or address. The team reviews it in the admin panel and
    contacts the applicant.
    """

    STATUS_CHOICES = (
        ("new", "New"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("rejected", "Rejected"),
    )

    full_name = models.CharField(max_length=150)

    phone = models.CharField(max_length=20)

    email = models.EmailField(blank=True)

    # Instagram or Telegram handle / link, as typed in the form
    social = models.CharField(
        max_length=255,
        blank=True
    )

    comment = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new"
    )

    # Set when the form is sent with a valid Bearer token
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_applications"
    )

    # Used to rate-limit the public form
    ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ip", "created_at"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
