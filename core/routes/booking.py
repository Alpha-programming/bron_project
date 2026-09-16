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
)

from core.services.booking import (
    create_booking,
    get_booking,
    get_user_bookings,
    update_booking,
    delete_booking,
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

    user = request.auth

    bookings = Booking.objects.filter(
        business_id=business_id
    ).select_related(
        "user",
        "service",
        "business",
        "branch",
        "staff"
    )

    # If business does not exist / no bookings,
    # owner validation is handled using first booking when available.
    first_booking = bookings.first()

    if first_booking:
        if (
            first_booking.business.owner_id != user.id
            and not user.is_staff
        ):
            raise HttpError(
                403,
                "Permission denied."
            )

    return bookings


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
    """

    return Booking.objects.filter(
        staff_id=staff_id
    ).select_related(
        "user",
        "service",
        "business",
        "branch",
        "staff"
    )


# ============================================================
# BOOKING DETAIL
# Dynamic routes start here.
# ============================================================

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

    booking = get_booking(
        booking_id
    )

    if booking.business.owner_id != request.auth.id:
        raise HttpError(
            403,
            "Only the business owner can approve this booking."
        )

    if booking.status != "pending":
        raise HttpError(
            400,
            "Only pending bookings can be approved."
        )

    booking.status = "confirmed"

    booking.save(
        update_fields=["status"]
    )

    return booking


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

    booking = get_booking(
        booking_id
    )

    if booking.business.owner_id != request.auth.id:
        raise HttpError(
            403,
            "Only the business owner can reject this booking."
        )

    if booking.status != "pending":
        raise HttpError(
            400,
            "Only pending bookings can be rejected."
        )

    booking.status = "rejected"

    booking.save(
        update_fields=["status"]
    )

    return booking


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

    user = request.auth

    if not user or hasattr(user, "_wrapped"):
        user = User.objects.get(
            id=request.user.id
        )

    booking = get_booking(
        booking_id
    )

    # Customer who created booking OR
    # business owner OR admin can cancel.
    if (
        booking.user_id != user.id
        and booking.business.owner_id != user.id
        and not user.is_staff
    ):
        raise HttpError(
            403,
            "Permission denied."
        )

    if booking.status in (
        "completed",
        "cancelled",
        "rejected"
    ):
        raise HttpError(
            400,
            f"Booking with status '{booking.status}' cannot be cancelled."
        )

    booking.status = "cancelled"

    booking.save(
        update_fields=["status"]
    )

    return booking


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