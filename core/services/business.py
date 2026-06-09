from ninja.errors import HttpError

from core.models import Business


def get_all_businesses():

    return Business.objects.select_related(
        "owner"
    ).all()


def get_business_by_id(
    business_id: int
):

    try:

        return Business.objects.select_related(
            "owner"
        ).get(
            id=business_id
        )

    except Business.DoesNotExist:

        raise HttpError(
            404,
            "Business not found"
        )


def create_business(
    user,
    data
):

    return Business.objects.create(
        owner=user,
        **data.model_dump()
    )


def update_business(
    user,
    business,
    data
):

    if business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    for field, value in data.model_dump(
        exclude_unset=True
    ).items():

        setattr(
            business,
            field,
            value
        )

    business.save()

    return business


def delete_business(
    user,
    business,
):

    if business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    business.delete()

    return {
        "message": "Business deleted successfully"
    }