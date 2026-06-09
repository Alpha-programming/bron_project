from ninja import Router

from core.schemas.booking import (
    BookingCreateSchema,
    BookingUpdateSchema,
    BookingOutSchema,
    BookingListSchema,
)

from core.services.booking import (
    create_booking,
    get_booking,
    get_user_bookings,
    update_booking,
    delete_booking,
)

from core.utils.auth import (
    get_current_user
)

router = Router(tags=["Bookings"])

@router.post(
    "/create",
    response=BookingOutSchema
)
def create_booking_view(
    request,
    payload: BookingCreateSchema
):

    user = get_current_user(
        request
    )

    return create_booking(
        user,
        payload
    )

@router.get(
    "/my",
    response=list[BookingListSchema]
)
def my_bookings(
    request
):

    user = get_current_user(
        request
    )

    return get_user_bookings(
        user
    )

@router.get(
    "/{booking_id}",
    response=BookingOutSchema
)
def booking_detail(
    request,
    booking_id: int
):

    return get_booking(
        booking_id
    )

@router.put(
    "/{booking_id}",
    response=BookingOutSchema
)
def update_booking_view(
    request,
    booking_id: int,
    payload: BookingUpdateSchema
):

    user = get_current_user(
        request
    )

    booking = get_booking(
        booking_id
    )

    return update_booking(
        user,
        booking,
        payload
    )

@router.delete(
    "/{booking_id}"
)
def delete_booking_view(
    request,
    booking_id: int
):

    user = get_current_user(
        request
    )

    booking = get_booking(
        booking_id
    )

    return delete_booking(
        user,
        booking
    )