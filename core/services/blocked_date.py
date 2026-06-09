from ninja.errors import HttpError

from core.models import (
    BlockedDate,
    Business,
)


def create_blocked_date(
    user,
    data
):

    try:

        business = Business.objects.get(
            id=data.business_id
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

    exists = BlockedDate.objects.filter(
        business=business,
        date=data.date
    ).exists()

    if exists:

        raise HttpError(
            400,
            "This date is already blocked"
        )

    return BlockedDate.objects.create(
        business=business,
        date=data.date,
        reason=data.reason,
    )


def get_business_blocked_dates(
    business_id
):

    return BlockedDate.objects.filter(
        business_id=business_id
    ).order_by(
        "date"
    )


def get_blocked_date(
    blocked_date_id
):

    try:

        return BlockedDate.objects.select_related(
            "business"
        ).get(
            id=blocked_date_id
        )

    except BlockedDate.DoesNotExist:

        raise HttpError(
            404,
            "Blocked date not found"
        )


def update_blocked_date(
    user,
    blocked_date,
    data
):

    if blocked_date.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    for field, value in data.model_dump(
        exclude_unset=True
    ).items():

        setattr(
            blocked_date,
            field,
            value
        )

    blocked_date.save()

    return blocked_date


def delete_blocked_date(
    user,
    blocked_date
):

    if blocked_date.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    blocked_date.delete()

    return {
        "message": "Blocked date deleted successfully"
    }