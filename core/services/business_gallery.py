from django.db.models import Max
from ninja.errors import HttpError

from core.models import (
    Business,
    BusinessGallery,
)

from core.utils.validators import validate_image

MAX_GALLERY_IMAGES = 20

# Upper bound of PositiveIntegerField in PostgreSQL
MAX_SORT_ORDER = 2147483647


def upload_business_image(
    user,
    business_id,
    image,
):

    try:

        business = Business.objects.get(
            id=business_id
        )

    except Business.DoesNotExist:

        raise HttpError(
            404,
            "Business not found"
        )

    if business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    validate_image(image)

    if business.gallery_images.count() >= MAX_GALLERY_IMAGES:

        raise HttpError(
            400,
            f"Gallery is limited to {MAX_GALLERY_IMAGES} images"
        )

    # New pictures go to the end of the gallery
    last = business.gallery_images.aggregate(
        last=Max("sort_order")
    )["last"]

    # A PUT may already have set the maximum; last + 1 would overflow the
    # PostgreSQL integer column, so ties there fall back to ordering by id
    return BusinessGallery.objects.create(
        business=business,
        image=image,
        sort_order=0 if last is None else min(last + 1, MAX_SORT_ORDER),
    )


def get_business_gallery(
    business_id,
):

    return BusinessGallery.objects.filter(
        business_id=business_id
    ).order_by(
        "sort_order",
        "id",
    )


def get_gallery_image(
    image_id,
):

    try:

        return BusinessGallery.objects.select_related(
            "business"
        ).get(
            id=image_id
        )

    except BusinessGallery.DoesNotExist:

        raise HttpError(
            404,
            "Image not found"
        )


def update_business_image(
    user,
    gallery_image,
    image=None,
    sort_order=None,
):

    if gallery_image.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    if image is None and sort_order is None:

        raise HttpError(
            400,
            "Provide image or sort_order"
        )

    if sort_order is not None:
        gallery_image.sort_order = sort_order

    old_name = None

    if image is not None:

        validate_image(image)

        old_name = gallery_image.image.name
        storage = gallery_image.image.storage

        gallery_image.image = image

    gallery_image.save()

    # Drop the replaced file only once the new one is saved
    if old_name and old_name != gallery_image.image.name:
        storage.delete(old_name)

    return gallery_image


def delete_business_image(
    user,
    image,
):

    if image.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    image.image.delete(
        save=False
    )

    image.delete()

    return {
        "message": "Image deleted successfully"
    }
