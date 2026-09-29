from django.db import models
from .business import Business


class BusinessGallery(models.Model):

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="gallery_images"
    )

    image = models.ImageField(
        upload_to="business_gallery/"
    )

    # Display position, lower first; ties go by id
    sort_order = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.business.name} Gallery"
