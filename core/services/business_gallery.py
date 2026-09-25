from ninja.errors import HttpError

from core.models import (
    Business,
    BusinessGallery,
)

from core.utils.validators import validate_image

MAX_GALLERY_IMAGES = 20


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

    return BusinessGallery.objects.create(
        business=business,
        image=image,
    )


def get_business_gallery(
    business_id,
):

    return BusinessGallery.objects.filter(
        business_id=business_id
    ).order_by(
        "-created_at"
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