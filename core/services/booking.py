from decimal import Decimal
from django.db import transaction
from datetime import datetime, date, time
from ninja.errors import HttpError
from django.utils import timezone

from core.models import (
    Booking,
    Business,
    Service,
    Branch,
    Staff,
    Product,
    BlockedDate,
)
from core.services.notification import notify
from core.services.service import booked_guests
from core.utils.helpers import working_day_bounds


def _parse_time(value):
    """
    Booking schema sends times as "HH:MM" strings; normalise to time objects
    so validation errors surface as 400 instead of a database error.
    """
    if isinstance(value, time):
        return value
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except (TypeError, ValueError):
            continue
    raise HttpError(400, "Time must be in HH:MM format")


def _can_view_booking(user, booking):
    return (
        booking.user_id == user.id
        or booking.business.owner_id == user.id
        or user.is_staff
    )


def create_booking(
    user,
    data
):

    try:

        business = Business.objects.select_related("owner").get(
            id=data.business_id
        )

        # Service and branch must belong to the same business
        service = Service.objects.get(
            id=data.service_id,
            business=business,
        )

        branch = Branch.objects.get(
            id=data.branch_id,
            business=business,
        )

    except (Business.DoesNotExist, Service.DoesNotExist, Branch.DoesNotExist):

        raise HttpError(
            404,
            "Business, service or branch not found"
        )

    if not business.is_active:

        raise HttpError(
            400,
            "Business is not accepting bookings yet"
        )

    blocked = BlockedDate.objects.filter(
        business=business,
        date=data.booking_date
    ).exists()

    if blocked:

        raise HttpError(
            400,
            "Selected date is blocked"
        )

    staff = None

    if data.staff_id:

        try:

            staff = Staff.objects.get(
                id=data.staff_id,
                business=business,
            )

        except Staff.DoesNotExist:

            raise HttpError(
                404,
                "Staff not found"
            )

    start_time = _parse_time(data.start_time)
    end_time = _parse_time(data.end_time)

    if end_time <= start_time:

        raise HttpError(
            400,
            "end_time must be after start_time"
        )

    if data.guest_count < 1:

        raise HttpError(
            400,
            "guest_count must be at least 1"
        )

    if data.guest_count > service.capacity:

        raise HttpError(
            400,
            f"This service allows at most {service.capacity} guests per slot"
        )

    with transaction.atomic():

        # Lock the service row so parallel bookings can't overbook the slot
        Service.objects.select_for_update().get(id=service.id)

        taken = booked_guests(
            service,
            data.booking_date,
            start_time,
            end_time,
        )

        if taken + data.guest_count > service.capacity:

            raise HttpError(
                400,
                f"Only {max(service.capacity - taken, 0)} places left for this time"
            )

        booking = _create_booking_record(
            user, business, service, branch, staff, data, start_time, end_time
        )

    return _finish_booking(user, business, service, booking, data)


def _create_booking_record(user, business, service, branch, staff, data, start_time, end_time):

    return Booking.objects.create(
        user=user,
        business=business,
        service=service,
        branch=branch,
        staff=staff,
        booking_date=data.booking_date,
        start_time=start_time,
        end_time=end_time,
        guest_count=data.guest_count,
        total_price=service.price,
    )


def _finish_booking(user, business, service, booking, data):

    total_price = Decimal(
        str(service.price)
    )

    if data.product_ids:

        products = Product.objects.filter(
            id__in=data.product_ids,
            business=business,
        )

        booking.products.set(
            products
        )

        for product in products:

            total_price += product.price

    booking.total_price = total_price
    booking.save()

    notify(
        business.owner,
        "booking_created",
        "New booking",
        f"{user.username} booked {service.title} on {booking.booking_date} at {booking.start_time:%H:%M}",
        booking=booking,
    )

    return booking


def get_booking_for_user(user, booking_id):
    """
    Booking visible only to its customer, the business owner or platform staff.
    """
    booking = get_booking(booking_id)

    if not _can_view_booking(user, booking):
        raise HttpError(403, "Permission denied")

    return booking


def get_business_bookings(user, business_id):
    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found")

    if business.owner_id != user.id and not user.is_staff:
        raise HttpError(403, "Permission denied")

    return Booking.objects.filter(
        business=business
    ).select_related("user", "service", "business", "branch", "staff")


def get_staff_bookings(user, staff_id):
    try:
        staff = Staff.objects.select_related("business").get(id=staff_id)
    except Staff.DoesNotExist:
        raise HttpError(404, "Staff not found")

    if staff.business.owner_id != user.id and not user.is_staff:
        raise HttpError(403, "Permission denied")

    return Booking.objects.filter(
        staff=staff
    ).select_related("user", "service", "business", "branch", "staff")


def approve_booking(user, booking):
    if booking.business.owner_id != user.id:
        raise HttpError(403, "Only the business owner can approve this booking.")

    if booking.status != "pending":
        raise HttpError(400, "Only pending bookings can be approved.")

    booking.status = "confirmed"
    booking.save(update_fields=["status"])

    notify(
        booking.user,
        "booking_confirmed",
        "Booking confirmed",
        f"{booking.business.name} confirmed your booking on {booking.booking_date} at {booking.start_time:%H:%M}",
        booking=booking,
    )

    return booking


def reject_booking(user, booking):
    if booking.business.owner_id != user.id:
        raise HttpError(403, "Only the business owner can reject this booking.")

    if booking.status != "pending":
        raise HttpError(400, "Only pending bookings can be rejected.")

    booking.status = "rejected"
    booking.save(update_fields=["status"])

    notify(
        booking.user,
        "booking_rejected",
        "Booking rejected",
        f"{booking.business.name} rejected your booking on {booking.booking_date} at {booking.start_time:%H:%M}",
        booking=booking,
    )

    return booking


def cancel_booking(user, booking):
    is_customer = booking.user_id == user.id
    is_owner = booking.business.owner_id == user.id

    if not (is_customer or is_owner or user.is_staff):
        raise HttpError(403, "Permission denied.")

    if booking.status in ("completed", "cancelled", "rejected"):
        raise HttpError(
            400,
            f"Booking with status '{booking.status}' cannot be cancelled."
        )

    booking.status = "cancelled"
    booking.save(update_fields=["status"])

    when = f"{booking.booking_date} at {booking.start_time:%H:%M}"

    # Tell the other side who cancelled
    if is_customer:
        notify(
            booking.business.owner,
            "booking_cancelled",
            "Booking cancelled",
            f"{booking.user.username} cancelled the booking on {when}",
            booking=booking,
        )
    else:
        notify(
            booking.user,
            "booking_cancelled",
            "Booking cancelled",
            f"{booking.business.name} cancelled your booking on {when}",
            booking=booking,
        )

    return booking


def get_booking(
    booking_id
):

    try:

        return Booking.objects.select_related(
            "user",
            "service",
            "business",
            "business__owner",
            "branch",
            "staff",
        ).get(
            id=booking_id
        )

    except Booking.DoesNotExist:

        raise HttpError(
            404,
            "Booking not found"
        )

def get_user_bookings(
    user
):

    return Booking.objects.filter(
        user=user
    ).order_by(
        "-created_at"
    )

def update_booking(
    user,
    booking,
    data
):

    if booking.user != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    if booking.status != "pending":

        raise HttpError(
            400,
            "Only pending bookings can be changed"
        )

    if data.staff_id is not None:

        try:

            booking.staff = Staff.objects.get(
                id=data.staff_id,
                business=booking.business,
            )

        except Staff.DoesNotExist:

            raise HttpError(
                404,
                "Staff not found"
            )

    booking.save()

    return booking

def delete_booking(
    user,
    booking
):

    if booking.user != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    booking.delete()

    return {
        "message": "Booking deleted successfully"
    }

from datetime import datetime, timedelta
from core.models import WorkingHours  # Ensure WorkingHours model is available or mocked correctly

def calculate_available_slots(business_id: int, staff_id: int, target_date: date) -> list:
    """
    Calculates operational 30-minute availability intervals on a target date.
    """
    # 1. Check global blockages
    blocked = BlockedDate.objects.filter(business_id=business_id, date=target_date).exists()
    if blocked:
        return []

    # 2. Extract day-of-week configuration (0 = Monday, 6 = Sunday)
    weekday = target_date.weekday()
    schedule = WorkingHours.objects.filter(business_id=business_id, day_of_week=weekday).first()
    if not schedule or schedule.is_closed:
        return []

    start_time = schedule.open_time
    end_time = schedule.close_time

    slots = []
    current_time, terminal_time = working_day_bounds(target_date, start_time, end_time)
    interval = timedelta(minutes=30)

    # 3. Pull concurrent booked targets
    existing_bookings = Booking.objects.filter(
        staff_id=staff_id,
        booking_date=target_date,
        status__in=["pending", "confirmed"]
    ).values_list('start_time', 'end_time')

    while current_time + interval <= terminal_time:
        slot_start = current_time.time()
        slot_end = (current_time + interval).time()

        is_taken = False
        for b_start, b_end in existing_bookings:
            # Handle standard time format data comparisons cleanly
            if not (slot_end <= b_start or slot_start >= b_end):
                is_taken = True
                break

        if not is_taken:
            slots.append(slot_start.strftime("%H:%M"))

        current_time += interval

    return slots

def update_booking_attendance(
    user,
    booking_id: int,
    status: str,
    extra_wait_minutes: int = 0
):
    allowed_statuses = {
        "visited",
        "late",
        "no_show",
    }

    if status not in allowed_statuses:
        raise HttpError(
            400,
            "Status must be visited, late or no_show."
        )

    try:
        booking = Booking.objects.select_related(
            "business",
            "user"
        ).get(id=booking_id)
    except Booking.DoesNotExist:
        raise HttpError(404, "Booking not found.")

    # Only this organization's owner can control attendance
    if booking.business.owner_id != user.id:
        raise HttpError(
            403,
            "Only the business owner can update attendance."
        )

    # Booking must first be accepted
    if booking.status != "confirmed":
        raise HttpError(
            400,
            "Booking must be confirmed first."
        )

    if status == "late":
        if extra_wait_minutes < 0:
            raise HttpError(
                400,
                "Extra wait minutes cannot be negative."
            )

        # Requirement currently mentions 10 minutes.
        if extra_wait_minutes > 10:
            raise HttpError(
                400,
                "Maximum extra waiting time is 10 minutes."
            )

    else:
        extra_wait_minutes = 0

    booking.attendance_status = status
    booking.extra_wait_minutes = extra_wait_minutes
    booking.attendance_updated_at = timezone.now()

    # Visited means appointment was completed.
    if status == "visited":
        booking.status = "completed"

    booking.save(
        update_fields=[
            "attendance_status",
            "extra_wait_minutes",
            "attendance_updated_at",
            "status",
        ]
    )

    return booking