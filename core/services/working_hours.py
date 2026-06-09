from ninja.errors import HttpError

from core.models import (
    WorkingHours,
    Business,
)


def create_working_hours(
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

    exists = WorkingHours.objects.filter(
        business=business,
        day_of_week=data.day_of_week
    ).exists()

    if exists:

        raise HttpError(
            400,
            "Working hours already exist for this day"
        )

    return WorkingHours.objects.create(
        business=business,
        day_of_week=data.day_of_week,
        open_time=data.open_time,
        close_time=data.close_time,
        is_closed=data.is_closed,
    )


def get_business_schedule(
    business_id
):

    return WorkingHours.objects.filter(
        business_id=business_id
    ).order_by(
        "day_of_week"
    )


def get_working_hours(
    working_hours_id
):

    try:

        return WorkingHours.objects.select_related(
            "business"
        ).get(
            id=working_hours_id
        )

    except WorkingHours.DoesNotExist:

        raise HttpError(
            404,
            "Working hours not found"
        )


def update_working_hours(
    user,
    working_hours,
    data
):

    if working_hours.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    for field, value in data.model_dump(
        exclude_unset=True
    ).items():

        setattr(
            working_hours,
            field,
            value
        )

    working_hours.save()

    return working_hours


def delete_working_hours(
    user,
    working_hours
):

    if working_hours.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    working_hours.delete()

    return {
        "message": "Working hours deleted successfully"
    }