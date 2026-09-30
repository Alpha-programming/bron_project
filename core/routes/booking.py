from typing import List, Optional
# The available-slots query parameter is called `date`
from datetime import date as date_type

from ninja import Query, Router

from core.security import JWTAuth
from core.models import User

from core.schemas.booking import (
    BookingCreateSchema,
    BookingUpdateSchema,
    BookingOutSchema,
    BookingListSchema,
    BookingAttendanceSchema,
    BookingRescheduleSchema,
    AvailableSlotsOutSchema,
)
from core.schemas.common import ErrorSchema
from core.schemas.service import SLOT_STAFF_DESCRIPTION

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
    get_available_slots as fetch_available_slots,
    update_booking_attendance,
)


router = Router(tags=["Bookings"])


# ============================================================
# CREATE BOOKING
# ============================================================

@router.post(
    "/create",
    auth=JWTAuth(),
    response={
        200: BookingOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        404: ErrorSchema,
    },
    summary="Create a booking",
)
def create_booking_view(
    request,
    payload: BookingCreateSchema
):
    """
    Books a service slot for the current user. Requires a Bearer token.

    Order: send `items` ({id, kind, quantity}); every item must be an active
    service or product of the same business. Duplicate lines are merged and
    the booked service is added with quantity 1 if missing. `name` and
    `price` in items are ignored: `total_price` is calculated on the server
    from current prices, and the order is saved in `items` of the booking.
    `product_ids` is deprecated and ignored when `items` is sent.

    Time: if the service has its own schedule, `start_time` must be one of
    the times listed for `booking_date` and `end_time` must be
    start_time + service duration.

    Places: `capacity` is shared by all bookings of the service, whichever
    staff member they are with. A chosen `staff_id` must also be free: it may
    not overlap another pending/confirmed booking of that staff member in any
    service (the same rule as `staff_id` in `GET /api/bookings/available-slots`).

    Errors:
    - 400: business not approved yet, blocked date, bad time format,
      end_time not after start_time, date/time outside the service schedule,
      guest_count out of range, not enough free places, staff member busy
      ("Selected time is not available: staff member is busy"), unknown or
      inactive item ("Item not found: product 12"), item quantity over 100.
    - 404: business, service, branch or staff not found in this business.
    - 422: request body does not match the schema.
    """
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

@router.get(
    "/available-slots",
    response={
        200: AvailableSlotsOutSchema,
        404: ErrorSchema,
    },
    summary="Available time slots for a service",
)
def get_available_slots(
    request,
    business_id: int = Query(..., description="Business id"),
    service_id: int = Query(..., description="Service of this business"),
    branch_id: int = Query(..., description="Branch of this business"),
    date: date_type = Query(..., description="Day to check, YYYY-MM-DD"),
    staff_id: Optional[int] = Query(None, description=SLOT_STAFF_DESCRIPTION),
):
    """
    Slots of `duration` minutes for one day, each with the number of free
    places (`capacity` minus guests of all pending/confirmed bookings of the
    service, whichever staff member they are with). Public, no token needed.

    With `staff_id`, slots overlapping a pending/confirmed booking of that
    staff member in any service are returned with `is_available: false` and
    `available_spots: 0`, so a slot shown as available can be booked with
    that staff member via `POST /api/bookings/create`.

    Slots come from the service's own schedule if it has one, otherwise from
    the business working hours. The list is empty on blocked or closed days,
    for past dates, for times that already started today and for a business
    that is not approved yet.

    Errors:
    - 404: business not found, or service, branch or staff not in this business.
    - 422: a required parameter is missing or `date` is not YYYY-MM-DD.
    """

    return fetch_available_slots(
        business_id,
        service_id,
        branch_id,
        date,
        staff_id,
    )


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
    response={
        200: BookingOutSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    summary="Booking details",
)
def booking_detail(
    request,
    booking_id: int
):
    """
    One booking with its order `items`. Requires a Bearer token; visible to
    the customer who made it, the business owner and platform staff (403
    for anyone else). 404 if the booking does not exist.
    """

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
    response={
        200: BookingOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
        409: ErrorSchema,
    },
    summary="Change the staff member of a booking",
)
def update_booking_view(
    request,
    booking_id: int,
    payload: BookingUpdateSchema
):
    """
    Assigns `staff_id` (a staff member of the same business) to a pending
    booking. Requires a Bearer token; the customer who made the booking only.
    The staff member must be free at the booking time, the same rule as in
    `POST /api/bookings/create`.

    Errors:
    - 400: the booking is not pending.
    - 403: not the customer of this booking.
    - 404: booking not found, or staff not found in this business.
    - 409: the staff member has another pending/confirmed booking (in any
      service) overlapping this one ("Selected time is not available: staff
      member is busy").
    """

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
    response={
        200: BookingOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
        409: ErrorSchema,
    },
    summary="Reschedule a booking",
)
def reschedule_booking_view(
    request,
    booking_id: int,
    payload: BookingRescheduleSchema
):
    """
    Moves a pending or confirmed booking to another date/time. Requires a
    Bearer token; allowed for the customer, the business owner and platform
    staff. A customer moving a confirmed booking sends it back to pending.

    If the service has its own schedule, the new `start_time` must be one of
    the times listed for `booking_date` and `end_time` must be
    start_time + service duration; the business working hours are not
    checked then. Otherwise the time must fit the working hours (when set).

    Errors:
    - 400: wrong status, bad time format, end_time not after start_time,
      time in the past, same time as now, blocked date, closed day,
      outside working hours or outside the service schedule.
    - 403: not the customer, owner or staff.
    - 404: booking not found.
    - 409: not enough free places, or the assigned staff member has another
      pending/confirmed booking (in any service) at the new time.
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
    response={
        200: BookingOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    summary="Mark customer attendance",
)
def update_booking_attendance_view(
    request,
    booking_id: int,
    payload: BookingAttendanceSchema
):
    """
    JWT auth, owner of the booking's business only.

    - `status`: `visited` (came on time), `late` or `no_show`.
    - `extra_wait_minutes`: only for `late`, 0-10; reset to 0 otherwise.
    - Allowed for a confirmed booking. `visited` sets the booking status to
      `completed`; the mark can still be changed later, and `late` / `no_show`
      then return the booking to `confirmed`.
    - The mark feeds the customer's `booking_rating`
      (GET /api/reviews/customer/{customer_id}/rating). A new mark replaces
      the previous one; sending the same mark again changes nothing.
    - Response: the booking with the saved `attendance_status`.

    Errors: 400 booking not confirmed, or extra_wait_minutes out of range;
    401 missing or invalid token; 403 not the business owner; 404 booking
    not found; 422 status is not visited, late or no_show.
    """

    return update_booking_attendance(
        request.auth,
        booking_id,
        payload.status,
        payload.extra_wait_minutes
    )