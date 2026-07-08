from ninja.errors import HttpError

from core.models import Business


def upload_logo(
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

    business.logo = image
    business.save()

    return business


def delete_logo(
    user,
    business_id,
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

    business.logo.delete(
        save=False
    )

    business.logo = None

    business.save()

    return {
        "message": "Logo deleted successfully"
    }