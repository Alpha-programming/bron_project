from decimal import Decimal
from datetime import datetime, date
from ninja.errors import HttpError

from core.models import (
    Booking,
    Business,
    Service,
    Branch,
    Staff,
    Product,
    BlockedDate,
)

def create_booking(
    user,
    data
):

    try:

        business = Business.objects.get(
            id=data.business_id
        )

        service = Service.objects.get(
            id=data.service_id
        )

        branch = Branch.objects.get(
            id=data.branch_id
        )

    except Exception:

        raise HttpError(
            404,
            "Business, service or branch not found"
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
                id=data.staff_id
            )

        except Staff.DoesNotExist:

            raise HttpError(
                404,
                "Staff not found"
            )

    booking = Booking.objects.create(
        user=user,
        business=business,
        service=service,
        branch=branch,
        staff=staff,
        booking_date=data.booking_date,
        start_time=data.start_time,
        end_time=data.end_time,
        guest_count=data.guest_count,
        total_price=service.price,
    )

    total_price = Decimal(
        str(service.price)
    )

    if data.product_ids:

        products = Product.objects.filter(
            id__in=data.product_ids
        )

        booking.products.set(
            products
        )

        for product in products:

            total_price += product.price

    booking.total_price = total_price
    booking.save()

    return booking

def get_booking(
    booking_id
):

    try:

        return Booking.objects.select_related(
            "user",
            "service",
            "business",
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

    if data.status is not None:

        booking.status = data.status

    if data.staff_id is not None:

        try:

            booking.staff = Staff.objects.get(
                id=data.staff_id
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
    if not schedule or not getattr(schedule, 'is_working_day', True):
        return []

    # Fallback default hours if fields aren't present in model definition
    start_time = getattr(schedule, 'start_time', datetime.strptime("09:00", "%H:%M").time())
    end_time = getattr(schedule, 'end_time', datetime.strptime("18:00", "%H:%M").time())

    slots = []
    current_time = datetime.combine(target_date, start_time)
    terminal_time = datetime.combine(target_date, end_time)
    interval = timedelta(minutes=30)

    # 3. Pull concurrent booked targets
    existing_bookings = Booking.objects.filter(
        staff_id=staff_id,
        booking_date=target_date,
        status__in=['PENDING', 'APPROVED', 'CONFIRMED']
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