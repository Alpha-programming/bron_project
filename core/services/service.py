from collections import defaultdict
from datetime import date as date_type, timedelta

from django.utils import timezone
from ninja.errors import HttpError

from core.models import BlockedDate, Booking, Business, Service, Staff, WorkingHours
from core.utils.helpers import working_day_bounds
from core.utils.schedule import (
    has_own_schedule,
    minutes_of,
    normalize_availability,
    schedule_slots,
    time_of,
)
from core.utils.validators import validate_image

# Bookings in these statuses occupy places in a slot
ACTIVE_BOOKING_STATUSES = ("pending", "confirmed")

MAX_AVAILABILITY_DAYS = 60


def _clean_availability(value, duration):
    """
    Canonical JSON-safe schedule (strings only) for Service.availability.
    The schema already checked the format; this adds the duration check,
    which only the service layer can do because the duration may come from
    the stored service.
    """
    try:
        return normalize_availability(value, duration)
    except ValueError as exc:
        raise HttpError(400, str(exc))


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
        availability=_clean_availability(data.availability, data.duration),
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

    fields = data.model_dump(exclude_unset=True)

    # Handled separately: the dump holds date objects, which a JSONField can't store
    availability_sent = "availability" in fields
    fields.pop("availability", None)

    for field, value in fields.items():
        setattr(service, field, value)

    if availability_sent:
        service.availability = _clean_availability(data.availability, service.duration)
    elif "duration" in fields and has_own_schedule(service):
        # A longer duration can push existing slots past 23:59
        service.availability = _clean_availability(service.availability, service.duration)

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


def booked_guests(service, day, start, end, exclude_booking_id=None):
    """
    Guests already booked into this service overlapping [start, end) on `day`.
    Capacity belongs to the service, so bookings with any staff member count.
    """
    qs = Booking.objects.filter(
        service=service,
        booking_date=day,
        status__in=ACTIVE_BOOKING_STATUSES,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_booking_id is not None:
        qs = qs.exclude(id=exclude_booking_id)
    return sum(qs.values_list("guest_count", flat=True))


def staff_is_busy(staff_id, day, start, end, exclude_booking_id=None):
    """
    True when the staff member has an active booking in any service
    overlapping [start, end) on `day`.
    """
    qs = Booking.objects.filter(
        staff_id=staff_id,
        booking_date=day,
        status__in=ACTIVE_BOOKING_STATUSES,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_booking_id is not None:
        qs = qs.exclude(id=exclude_booking_id)
    return qs.exists()


def _resolve_staff(service, staff_id):
    if staff_id is None:
        return None
    try:
        return Staff.objects.get(id=staff_id, business_id=service.business_id)
    except Staff.DoesNotExist:
        raise HttpError(404, "Staff not found")


def _working_hours_slots(service, day, hours):
    """
    Consecutive (start, end) pairs of `service.duration` minutes inside the
    day's working hours.
    """
    if hours is None or hours.is_closed:
        return []

    duration = service.duration
    # Zero is possible via the ORM (PositiveIntegerField) and has no slots
    if duration is None or duration < 1:
        return []

    opening, closing = working_day_bounds(day, hours.open_time, hours.close_time)

    # Minute arithmetic: datetime + timedelta overflows on 9999-12-31.
    # Rounded inwards so no slot starts before opening or ends after closing.
    first = minutes_of(opening) + (1 if opening.second or opening.microsecond else 0)
    last = minutes_of(closing)

    return [
        (time_of(start), time_of(start + duration))
        for start in range(first, last - duration + 1, duration)
    ]


def _candidate_slots(service, day, hours):
    """
    (start, end) pairs the service offers on `day`: its own schedule when it
    has one (working hours are ignored then), otherwise the working hours.
    """
    own = schedule_slots(service, day)
    if own is not None:
        return own
    return _working_hours_slots(service, day, hours)


def _build_slots(service, day, hours, bookings, staff_busy, now):
    """
    Bookable slots of the day with the places left in each.
    `bookings` is a list of (start_time, end_time, guest_count) of all active
    bookings of the service that day; `staff_busy` is a list of
    (start_time, end_time) when the chosen staff member is already booked
    (in any service), empty when no staff member was chosen.
    Mirrors the checks of create_booking, so a free slot can be booked.
    """
    slots = []
    for slot_start, slot_end in _candidate_slots(service, day, hours):
        # Slots that already started today can't be booked
        if day == now.date() and slot_start <= now.time():
            continue

        taken = sum(
            guests for b_start, b_end, guests in bookings
            if b_start < slot_end and b_end > slot_start
        )
        left = max(service.capacity - taken, 0)

        if any(b_start < slot_end and b_end > slot_start for b_start, b_end in staff_busy):
            left = 0

        slots.append({
            "start_time": slot_start.strftime("%H:%M"),
            "end_time": slot_end.strftime("%H:%M"),
            "available_spots": left,
            "is_available": left > 0,
        })

    return slots


def _load_schedule(service, date_from, date_to, staff):
    # Working hours don't matter for a service with its own schedule
    hours_by_weekday = {} if has_own_schedule(service) else {
        h.day_of_week: h
        for h in WorkingHours.objects.filter(business_id=service.business_id)
    }
    blocked = set(
        BlockedDate.objects.filter(
            business_id=service.business_id,
            date__range=(date_from, date_to),
        ).values_list("date", flat=True)
    )

    # Places are counted over every booking of the service, whoever the
    # staff member is, the same way booked_guests does at booking time
    bookings_by_day = defaultdict(list)
    for day, start, end, guests in Booking.objects.filter(
        service=service,
        booking_date__range=(date_from, date_to),
        status__in=ACTIVE_BOOKING_STATUSES,
    ).values_list("booking_date", "start_time", "end_time", "guest_count"):
        bookings_by_day[day].append((start, end, guests))

    # A chosen staff member is also taken by their bookings in other services
    staff_busy_by_day = defaultdict(list)
    if staff is not None:
        for day, start, end in Booking.objects.filter(
            staff=staff,
            booking_date__range=(date_from, date_to),
            status__in=ACTIVE_BOOKING_STATUSES,
        ).values_list("booking_date", "start_time", "end_time"):
            staff_busy_by_day[day].append((start, end))

    return hours_by_weekday, blocked, bookings_by_day, staff_busy_by_day


def get_service_availability(service, day: date_type, staff_id=None):
    """
    Slots of one day. available_spots is capacity minus guests of all active
    bookings of the service; with staff_id, slots overlapping an active
    booking of that staff member (any service) get 0 places.
    """
    staff = _resolve_staff(service, staff_id)
    now = timezone.localtime()

    slots = []
    if day >= now.date():
        hours_by_weekday, blocked, bookings_by_day, staff_busy_by_day = _load_schedule(
            service, day, day, staff
        )
        if day not in blocked:
            slots = _build_slots(
                service,
                day,
                hours_by_weekday.get(day.weekday()),
                bookings_by_day[day],
                staff_busy_by_day[day],
                now,
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
    Dates from today on which the service has at least one free slot,
    following the service's own schedule when it has one. Free means the
    same as in get_service_availability, including the staff_id rule.
    """
    if days < 1 or days > MAX_AVAILABILITY_DAYS:
        raise HttpError(400, f"days must be between 1 and {MAX_AVAILABILITY_DAYS}")

    staff = _resolve_staff(service, staff_id)
    now = timezone.localtime()
    date_from = now.date()
    date_to = date_from + timedelta(days=days - 1)

    hours_by_weekday, blocked, bookings_by_day, staff_busy_by_day = _load_schedule(
        service, date_from, date_to, staff
    )

    result = []
    for offset in range(days):
        day = date_from + timedelta(days=offset)
        if day in blocked:
            continue
        slots = _build_slots(
            service,
            day,
            hours_by_weekday.get(day.weekday()),
            bookings_by_day[day],
            staff_busy_by_day[day],
            now,
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