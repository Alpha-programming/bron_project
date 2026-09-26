from typing import List
from datetime import date

from ninja import Router
from ninja.errors import HttpError

from core.security import JWTAuth
from core.models import User, Booking

from core.schemas.booking import (
    BookingCreateSchema,
    BookingUpdateSchema,
    BookingOutSchema,
    BookingListSchema,
    BookingAttendanceSchema,
    BookingRescheduleSchema,
)

from core.services.booking import (
    create_booking,
    get_booking,
    get_booking_for_user,
    get_user_bookings,
    get_business_bookings as fetch_business_bookings,
    get_staff_bookings as fetch_staff_bookings,
    update_booking,
    delete_booking,
    approve_booking as approve,
    reject_booking as reject,
    cancel_booking as cancel,
    reschedule_booking,
    calculate_available_slots,
    update_booking_attendance,
)


router = Router(tags=["Bookings"])


# ============================================================
# CREATE BOOKING
# ============================================================

@router.post(
    "/create",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def create_booking_view(
    request,
    payload: BookingCreateSchema
):
    user = request.auth

    if not user or hasattr(user, "_wrapped"):
        user = User.objects.get(
            id=request.user.id
        )

    return create_booking(
        user,
        payload
    )


# ============================================================
# MY BOOKINGS
# ============================================================

@router.get(
    "/my",
    auth=JWTAuth(),
    response=List[BookingListSchema]
)
def my_bookings(request):

    user = request.auth

    if not user or hasattr(user, "_wrapped"):
        user = User.objects.get(
            id=request.user.id
        )

    return get_user_bookings(user)


# ============================================================
# AVAILABLE SLOTS
# IMPORTANT:
# Keep this BEFORE /{booking_id}
# ============================================================

@router.get("/available-slots")
def get_available_slots(
    request,
    business_id: int,
    staff_id: int,
    target_date: date
):
    """
    Get available time slots for a specific date.
    """

    slots = calculate_available_slots(
        business_id,
        staff_id,
        target_date
    )

    return {
        "date": target_date,
        "available_slots": slots
    }


# ============================================================
# BUSINESS BOOKINGS
# ============================================================

@router.get(
    "/business/{business_id}",
    auth=JWTAuth(),
    response=List[BookingOutSchema]
)
def get_business_bookings(
    request,
    business_id: int
):
    """
    Get all bookings belonging to a business.
    Only the business owner can access them.
    """

    return fetch_business_bookings(
        request.auth,
        business_id
    )


# ============================================================
# STAFF BOOKINGS
# ============================================================

@router.get(
    "/staff/{staff_id}",
    auth=JWTAuth(),
    response=List[BookingOutSchema]
)
def get_staff_bookings(
    request,
    staff_id: int
):
    """
    Get bookings assigned to a staff member.
    Only the owner of the staff member's business can access them.
    """

    return fetch_staff_bookings(
        request.auth,
        staff_id
    )


# ============================================================
# BOOKING DETAIL
# Dynamic routes start here.
# ============================================================

@router.get(
    "/{booking_id}",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def booking_detail(
    request,
    booking_id: int
):

    return get_booking_for_user(
        request.auth,
        booking_id
    )


# ============================================================
# UPDATE BOOKING
# ============================================================

@router.put(
    "/{booking_id}",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def update_booking_view(
    request,
    booking_id: int,
    payload: BookingUpdateSchema
):

    user = request.auth

    if not user or hasattr(user, "_wrapped"):
        user = User.objects.get(
            id=request.user.id
        )

    booking = get_booking(
        booking_id
    )

    return update_booking(
        user,
        booking,
        payload
    )


# ============================================================
# DELETE BOOKING
# ============================================================

@router.delete(
    "/{booking_id}",
    auth=JWTAuth()
)
def delete_booking_view(
    request,
    booking_id: int
):

    user = request.auth

    if not user or hasattr(user, "_wrapped"):
        user = User.objects.get(
            id=request.user.id
        )

    booking = get_booking(
        booking_id
    )

    return delete_booking(
        user,
        booking
    )


# ============================================================
# APPROVE BOOKING
# ============================================================

@router.patch(
    "/{booking_id}/approve",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def approve_booking(
    request,
    booking_id: int
):

    return approve(
        request.auth,
        get_booking(booking_id)
    )


# ============================================================
# REJECT BOOKING
# ============================================================

@router.patch(
    "/{booking_id}/reject",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def reject_booking(
    request,
    booking_id: int
):

    return reject(
        request.auth,
        get_booking(booking_id)
    )


# ============================================================
# CANCEL BOOKING
# ============================================================

@router.patch(
    "/{booking_id}/cancel",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def cancel_booking_view(
    request,
    booking_id: int
):

    return cancel(
        request.auth,
        get_booking(booking_id)
    )


# ============================================================
# RESCHEDULE BOOKING
# ============================================================

@router.patch(
    "/{booking_id}/reschedule",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def reschedule_booking_view(
    request,
    booking_id: int,
    payload: BookingRescheduleSchema
):
    """
    Move a booking to another date/time.
    409 if the new slot is already taken.
    """

    return reschedule_booking(
        request.auth,
        get_booking(booking_id),
        payload
    )


# ============================================================
# ATTENDANCE
#
# Supported:
# visited
# late
# no_show
# ============================================================

@router.patch(
    "/{booking_id}/attendance",
    auth=JWTAuth(),
    response=BookingOutSchema
)
def update_booking_attendance_view(
    request,
    booking_id: int,
    payload: BookingAttendanceSchema
):

    return update_booking_attendance(
        request.auth,
        booking_id,
        payload.status,
        payload.extra_wait_minutes
    )