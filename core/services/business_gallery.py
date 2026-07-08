from ninja.errors import HttpError

from core.models import (
    Business,
    BusinessGallery,
)


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

    image.delete()

    return {
        "message": "Image deleted successfully"
    }