from ninja.errors import HttpError

from core.models import (
    Staff,
    Business,
)


def create_staff(
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

    return Staff.objects.create(
        business=business,
        full_name=data.full_name,
        position=data.position,
        phone=data.phone or "",
    )


def get_staff_list():

    return Staff.objects.select_related(
        "business"
    ).all()


def get_staff(
    staff_id
):

    try:

        return Staff.objects.select_related(
            "business"
        ).get(
            id=staff_id
        )

    except Staff.DoesNotExist:

        raise HttpError(
            404,
            "Staff not found"
        )


def get_business_staff(
    business_id
):

    return Staff.objects.filter(
        business_id=business_id
    )


def update_staff(
    user,
    staff,
    data
):

    if staff.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    for field, value in data.model_dump(
        exclude_unset=True
    ).items():

        setattr(
            staff,
            field,
            value
        )

    staff.save()

    return staff


def delete_staff(
    user,
    staff
):

    if staff.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    staff.delete()

    return {
        "message": "Staff deleted successfully"
    }