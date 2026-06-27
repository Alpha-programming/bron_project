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
)
from core.services.booking import (
    create_booking,
    get_booking,
    get_user_bookings,
    update_booking,
    delete_booking,
    calculate_available_slots,  # Coming in services file update below
)

router = Router(tags=["Bookings"])


# --- EXISTING VIEW ENGINES ---

@router.post("/create", auth=JWTAuth(), response=BookingOutSchema)
def create_booking_view(request, payload: BookingCreateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_booking(user, payload)


@router.get("/my", auth=JWTAuth(), response=List[BookingListSchema])
def my_bookings(request):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return get_user_bookings(user)


@router.get("/{booking_id}", response=BookingOutSchema)
def booking_detail(request, booking_id: int):
    return get_booking(booking_id)


@router.put("/{booking_id}", auth=JWTAuth(), response=BookingOutSchema)
def update_booking_view(request, booking_id: int, payload: BookingUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    booking = get_booking(booking_id)
    return update_booking(user, booking, payload)


@router.delete("/{booking_id}", auth=JWTAuth())
def delete_booking_view(request, booking_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    booking = get_booking(booking_id)
    return delete_booking(user, booking)


# --- MISSING MVP HOOKS ---

@router.get("/business/{business_id}", auth=JWTAuth(), response=List[BookingOutSchema])
def get_business_bookings(request, business_id: int):
    """
    Get all bookings for a business.
    """
    return Booking.objects.filter(business_id=business_id).select_related("user", "service", "branch", "staff")


@router.get("/staff/{staff_id}", auth=JWTAuth(), response=List[BookingOutSchema])
def get_staff_bookings(request, staff_id: int):
    """
    Get all bookings assigned to a staff member.
    """
    return Booking.objects.filter(staff_id=staff_id).select_related("user", "service", "business", "branch")


@router.get("/available-slots")
def get_available_slots(request, business_id: int, staff_id: int, target_date: date):
    """
    Get available time slots for a specific date.
    """
    slots = calculate_available_slots(business_id, staff_id, target_date)
    return {"date": target_date, "available_slots": slots}


@router.patch("/{booking_id}/approve", auth=JWTAuth(), response=BookingOutSchema)
def approve_booking(request, booking_id: int):
    """
    Approve a booking.
    """
    booking = get_booking(booking_id)
    booking.status = "APPROVED"
    booking.save()
    return booking


@router.patch("/{booking_id}/reject", auth=JWTAuth(), response=BookingOutSchema)
def reject_booking(request, booking_id: int):
    """
    Reject a booking.
    """
    booking = get_booking(booking_id)
    booking.status = "REJECTED"
    booking.save()
    return booking


@router.patch("/{booking_id}/cancel", auth=JWTAuth(), response=BookingOutSchema)
def cancel_booking_view(request, booking_id: int):
    """
    Cancel booking securely without deleting history records.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    booking = get_booking(booking_id)
    if not user.is_staff and booking.user != user:
        raise HttpError(403, "Permission denied")

    booking.status = "CANCELLED"
    booking.save()
    return booking