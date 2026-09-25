from collections import defaultdict
from datetime import date as date_type, datetime, timedelta

from django.utils import timezone
from ninja.errors import HttpError

from core.models import BlockedDate, Booking, Business, Service, Staff, WorkingHours
from core.utils.helpers import working_day_bounds
from core.utils.validators import validate_image

# Bookings in these statuses occupy places in a slot
ACTIVE_BOOKING_STATUSES = ("pending", "confirmed")

MAX_AVAILABILITY_DAYS = 60

def create_service(user, data):
    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found")

    if business.owner != user:
        raise HttpError(403, "Permission denied")

    return Service.objects.create(
        business=business,
        title=data.title,
        description=data.description,
        category=data.category,
        duration=data.duration,
        price=data.price,
        capacity=data.capacity,
    )

def get_services():
    return Service.objects.filter(is_active=True).select_related("business")

def get_service(service_id: int):
    try:
        return Service.objects.select_related("business", "business__owner").get(id=service_id)
    except Service.DoesNotExist:
        raise HttpError(404, "Service not found")

def get_business_services(business_id: int):
    return Service.objects.filter(business_id=business_id, is_active=True)

def update_service(user, service, data):
    if service.business.owner != user:
        raise HttpError(403, "Permission denied")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)

    service.save()
    return service

def upload_service_image(user, service, image):
    if service.business.owner != user:
        raise HttpError(403, "Permission denied")

    validate_image(image)

    if service.image:
        service.image.delete(save=False)

    service.image = image
    service.save(update_fields=["image"])
    return service


def delete_service_image(user, service):
    if service.business.owner != user:
        raise HttpError(403, "Permission denied")

    if service.image:
        service.image.delete(save=False)

    service.image = None
    service.save(update_fields=["image"])
    return service


def booked_guests(service, day, start, end, staff=None, exclude_booking_id=None):
    """
    Guests already booked into this service overlapping [start, end) on `day`.
    """
    qs = Booking.objects.filter(
        service=service,
        booking_date=day,
        status__in=ACTIVE_BOOKING_STATUSES,
        start_time__lt=end,
        end_time__gt=start,
    )
    if staff is not None:
        qs = qs.filter(staff=staff)
    if exclude_booking_id is not None:
        qs = qs.exclude(id=exclude_booking_id)
    return sum(qs.values_list("guest_count", flat=True))


def _resolve_staff(service, staff_id):
    if staff_id is None:
        return None
    try:
        return Staff.objects.get(id=staff_id, business_id=service.business_id)
    except Staff.DoesNotExist:
        raise HttpError(404, "Staff not found")


def _build_slots(service, day, hours, bookings, now):
    """
    Slots of `service.duration` minutes inside the day's working hours.
    `bookings` is a list of (start_time, end_time, guest_count) for that day.
    """
    if hours is None or hours.is_closed:
        return []

    step = timedelta(minutes=service.duration)
    current, closing = working_day_bounds(day, hours.open_time, hours.close_time)

    slots = []
    while current + step <= closing:
        slot_start = current.time()
        slot_end = (current + step).time()
        current += step

        # Slots that already started today can't be booked
        if day == now.date() and slot_start <= now.time():
            continue

        taken = sum(
            guests for b_start, b_end, guests in bookings
            if b_start < slot_end and b_end > slot_start
        )
        left = max(service.capacity - taken, 0)

        slots.append({
            "start_time": slot_start.strftime("%H:%M"),
            "end_time": slot_end.strftime("%H:%M"),
            "available_spots": left,
            "is_available": left > 0,
        })

    return slots


def _load_schedule(service, date_from, date_to, staff):
    hours_by_weekday = {
        h.day_of_week: h
        for h in WorkingHours.objects.filter(business_id=service.business_id)
    }
    blocked = set(
        BlockedDate.objects.filter(
            business_id=service.business_id,
            date__range=(date_from, date_to),
        ).values_list("date", flat=True)
    )

    bookings_qs = Booking.objects.filter(
        service=service,
        booking_date__range=(date_from, date_to),
        status__in=ACTIVE_BOOKING_STATUSES,
    )
    if staff is not None:
        bookings_qs = bookings_qs.filter(staff=staff)

    bookings_by_day = defaultdict(list)
    for day, start, end, guests in bookings_qs.values_list(
        "booking_date", "start_time", "end_time", "guest_count"
    ):
        bookings_by_day[day].append((start, end, guests))

    return hours_by_weekday, blocked, bookings_by_day


def get_service_availability(service, day: date_type, staff_id=None):
    staff = _resolve_staff(service, staff_id)
    now = timezone.localtime()

    slots = []
    if day >= now.date():
        hours_by_weekday, blocked, bookings_by_day = _load_schedule(service, day, day, staff)
        if day not in blocked:
            slots = _build_slots(
                service, day, hours_by_weekday.get(day.weekday()), bookings_by_day[day], now
            )

    return {
        "service_id": service.id,
        "date": day,
        "duration": service.duration,
        "capacity": service.capacity,
        "slots": slots,
    }


def get_service_available_dates(service, days: int = 14, staff_id=None):
    """
    Dates from today on which the service has at least one free slot.
    """
    if days < 1 or days > MAX_AVAILABILITY_DAYS:
        raise HttpError(400, f"days must be between 1 and {MAX_AVAILABILITY_DAYS}")

    staff = _resolve_staff(service, staff_id)
    now = timezone.localtime()
    date_from = now.date()
    date_to = date_from + timedelta(days=days - 1)

    hours_by_weekday, blocked, bookings_by_day = _load_schedule(service, date_from, date_to, staff)

    result = []
    for offset in range(days):
        day = date_from + timedelta(days=offset)
        if day in blocked:
            continue
        slots = _build_slots(
            service, day, hours_by_weekday.get(day.weekday()), bookings_by_day[day], now
        )
        free = sum(1 for s in slots if s["is_available"])
        if free:
            result.append({"date": day, "free_slots": free})

    return result


def delete_service(user, service):
    if service.business.owner != user:
        raise HttpError(403, "Permission denied")

    service.delete()
    return {"message": "Service deleted successfully"}

def get_distinct_service_categories() -> list[str]:
    """
    Returns a unique list of all active service categories currently on the platform.
    """
    return list(
        Service.objects.filter(is_active=True)
        .values_list("category", flat=True)
        .distinct()
    )