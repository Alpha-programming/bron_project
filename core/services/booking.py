from decimal import Decimal
from django.db import transaction
from datetime import datetime, time
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
    WorkingHours,
)
from core.schemas.booking import MAX_ITEM_QUANTITY
from core.services.notification import notify
from core.services.service import booked_guests, get_service_availability, staff_is_busy
from core.utils.helpers import working_day_bounds
from core.utils.schedule import check_service_schedule

CENT = Decimal("0.01")

# Booking.total_price is DecimalField(max_digits=10, decimal_places=2)
MAX_TOTAL_PRICE = Decimal("99999999.99")


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

    check_service_schedule(service, data.booking_date, start_time, end_time)

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

    # Priced before the row exists so a bad item never leaves a booking behind
    items, total_price, products = _price_order(business, service, data)

    with transaction.atomic():

        # Lock the service row so parallel bookings can't overbook the slot
        Service.objects.select_for_update().get(id=service.id)

        if staff is not None:
            # Locked after the service (same order as reschedule): bookings of
            # other services can't take the same staff member in parallel
            Staff.objects.select_for_update().get(id=staff.id)

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

        # The staff member can't be in two bookings at once, in any service
        if staff is not None and staff_is_busy(
            staff.id,
            data.booking_date,
            start_time,
            end_time,
        ):

            raise HttpError(
                400,
                "Selected time is not available: staff member is busy"
            )

        booking = Booking.objects.create(
            user=user,
            business=business,
            service=service,
            branch=branch,
            staff=staff,
            booking_date=data.booking_date,
            start_time=start_time,
            end_time=end_time,
            guest_count=data.guest_count,
            total_price=total_price,
            items=items,
        )

        booking.products.set(products)

    notify(
        business.owner,
        "booking_created",
        "New booking",
        f"{user.username} booked {service.title} on {booking.booking_date} at {booking.start_time:%H:%M}",
        booking=booking,
    )

    return booking


def _price_order(business, service, data):
    """
    Order lines priced from the database; any name/price sent by the client
    is ignored. Returns (items snapshot, total_price, products).

    With `items` every line must be an active service or product of the
    business, else 400. Legacy clients send only product_ids, where unknown
    ids are skipped as before.
    """
    main = ("service", service.id)

    if data.items:
        strict = True
        requested = {}
        for item in data.items:
            key = (item.kind, item.id)
            requested[key] = requested.get(key, 0) + item.quantity
        if main not in requested:
            requested = {main: 1, **requested}
    else:
        strict = False
        requested = {main: 1}
        for product_id in data.product_ids:
            requested.setdefault(("product", product_id), 1)

    service_ids = {obj_id for kind, obj_id in requested if kind == "service"} - {service.id}
    product_ids = {obj_id for kind, obj_id in requested if kind == "product"}

    catalogue = {
        ("service", obj.id): obj
        for obj in Service.objects.filter(id__in=service_ids, business=business, is_active=True)
    }
    catalogue.update(
        (("product", obj.id), obj)
        for obj in Product.objects.filter(id__in=product_ids, business=business, is_active=True)
    )
    # The booked service itself was already checked against the business
    catalogue[main] = service

    items, products, total = [], [], Decimal("0")

    for (kind, obj_id), quantity in requested.items():
        obj = catalogue.get((kind, obj_id))

        if obj is None:
            if strict:
                raise HttpError(400, f"Item not found: {kind} {obj_id}")
            continue

        if quantity > MAX_ITEM_QUANTITY:
            raise HttpError(
                400,
                f"Quantity of {kind} {obj_id} must be at most {MAX_ITEM_QUANTITY}"
            )

        price = obj.price.quantize(CENT)
        total += price * quantity

        items.append({
            "id": obj.id,
            "name": obj.title if kind == "service" else obj.name,
            "price": str(price),
            "quantity": quantity,
            "kind": kind,
        })

        if kind == "product":
            products.append(obj)

    if total > MAX_TOTAL_PRICE:
        raise HttpError(400, "Order total is too large")

    return items, total, products


def get_available_slots(business_id, service_id, branch_id, day, staff_id=None):
    """
    Free slots of a service for one day, with the booking context echoed back.
    A business that is not approved yet has no slots.
    """
    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found")

    try:
        service = Service.objects.get(id=service_id, business=business)
    except Service.DoesNotExist:
        raise HttpError(404, "Service not found")

    if not Branch.objects.filter(id=branch_id, business=business).exists():
        raise HttpError(404, "Branch not found")

    if staff_id is not None and not Staff.objects.filter(id=staff_id, business=business).exists():
        raise HttpError(404, "Staff not found")

    slots = []
    if business.is_active:
        slots = get_service_availability(service, day, staff_id)["slots"]

    return {
        "business_id": business.id,
        "service_id": service.id,
        "branch_id": branch_id,
        "staff_id": staff_id,
        "date": day,
        "duration": service.duration,
        "capacity": service.capacity,
        "slots": slots,
    }


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


RESCHEDULABLE_STATUSES = ("pending", "confirmed")


def reschedule_booking(user, booking, data):
    """
    Moves a booking to a new date/time after checking the new slot is free.
    Customer or business owner only. A customer moving a confirmed booking
    sends it back to "pending" so the owner re-approves the new time.
    """
    is_customer = booking.user_id == user.id
    is_owner = booking.business.owner_id == user.id

    if not (is_customer or is_owner or user.is_staff):
        raise HttpError(403, "Permission denied")

    if booking.status not in RESCHEDULABLE_STATUSES:
        raise HttpError(
            400,
            f"Booking with status '{booking.status}' cannot be rescheduled"
        )

    new_date = data.booking_date
    start_time = _parse_time(data.start_time)
    end_time = _parse_time(data.end_time)

    if end_time <= start_time:
        raise HttpError(400, "end_time must be after start_time")

    now = timezone.localtime()
    if new_date < now.date() or (new_date == now.date() and start_time <= now.time()):
        raise HttpError(400, "Cannot reschedule to a time in the past")

    if (
        new_date == booking.booking_date
        and start_time == booking.start_time
        and end_time == booking.end_time
    ):
        raise HttpError(400, "Booking is already at this time")

    business = booking.business

    if BlockedDate.objects.filter(business=business, date=new_date).exists():
        raise HttpError(400, "Selected date is blocked")

    service = booking.service

    # A service with its own schedule is bookable only at the listed times,
    # which replace the business working hours
    on_schedule = check_service_schedule(service, new_date, start_time, end_time)

    # Only enforce working hours when the business has configured them
    if not on_schedule and WorkingHours.objects.filter(business=business).exists():
        hours = WorkingHours.objects.filter(
            business=business,
            day_of_week=new_date.weekday(),
        ).first()

        if hours is None or hours.is_closed:
            raise HttpError(400, "Business is closed on this day")

        opening, closing = working_day_bounds(new_date, hours.open_time, hours.close_time)
        if (
            datetime.combine(new_date, start_time) < opening
            or datetime.combine(new_date, end_time) > closing
        ):
            raise HttpError(
                400,
                f"Time must be within working hours {opening:%H:%M}-{closing:%H:%M}"
            )

    with transaction.atomic():

        # Same locks and order as create_booking so a reschedule and a new
        # booking can't both take the last place or the same staff member
        Service.objects.select_for_update().get(id=service.id)

        if booking.staff_id:
            Staff.objects.select_for_update().get(id=booking.staff_id)

        taken = booked_guests(
            service,
            new_date,
            start_time,
            end_time,
            exclude_booking_id=booking.id,
        )

        if taken + booking.guest_count > service.capacity:
            raise HttpError(
                409,
                f"Selected time is not available: only {max(service.capacity - taken, 0)} places left"
            )

        # The assigned staff member can't be in two bookings at once
        if booking.staff_id and staff_is_busy(
            booking.staff_id,
            new_date,
            start_time,
            end_time,
            exclude_booking_id=booking.id,
        ):
            raise HttpError(409, "Selected time is not available: staff member is busy")

        old_when = f"{booking.booking_date} at {booking.start_time:%H:%M}"

        booking.booking_date = new_date
        booking.start_time = start_time
        booking.end_time = end_time

        update_fields = ["booking_date", "start_time", "end_time"]

        if is_customer and booking.status == "confirmed":
            booking.status = "pending"
            update_fields.append("status")

        booking.save(update_fields=update_fields)

    new_when = f"{new_date} at {start_time:%H:%M}"

    # Tell the other side
    if is_customer:
        notify(
            business.owner,
            "booking_rescheduled",
            "Booking rescheduled",
            f"{booking.user.username} moved the booking from {old_when} to {new_when}",
            booking=booking,
        )
    else:
        notify(
            booking.user,
            "booking_rescheduled",
            "Booking rescheduled",
            f"{business.name} moved your booking from {old_when} to {new_when}",
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

    with transaction.atomic():

        if data.staff_id is not None:

            try:

                # Same staff lock as create/reschedule, so parallel requests
                # can't give one staff member overlapping bookings
                staff = Staff.objects.select_for_update().get(
                    id=data.staff_id,
                    business=booking.business,
                )

            except Staff.DoesNotExist:

                raise HttpError(
                    404,
                    "Staff not found"
                )

            # The staff member can't be in two bookings at once, in any service
            if staff_is_busy(
                staff.id,
                booking.booking_date,
                booking.start_time,
                booking.end_time,
                exclude_booking_id=booking.id,
            ):
                raise HttpError(409, "Selected time is not available: staff member is busy")

            booking.staff = staff

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

ATTENDANCE_STATUSES = ("visited", "late", "no_show")

# Bookings the business accepted; "completed" comes from a visited mark
MARKABLE_STATUSES = ("confirmed", "completed")

MAX_EXTRA_WAIT_MINUTES = 10


def update_booking_attendance(
    user,
    booking_id: int,
    status: str,
    extra_wait_minutes: int = 0
):
    """
    Marks how the customer showed up. The customer's booking rating is built
    from the current mark of each booking (customer_booking_rating), so a new
    mark replaces the previous one and repeating a mark changes nothing.
    """
    if status not in ATTENDANCE_STATUSES:
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

    # Booking must first be accepted; an already marked one can be re-marked
    if booking.status not in MARKABLE_STATUSES:
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

        if extra_wait_minutes > MAX_EXTRA_WAIT_MINUTES:
            raise HttpError(
                400,
                f"Maximum extra waiting time is {MAX_EXTRA_WAIT_MINUTES} minutes."
            )

    else:
        extra_wait_minutes = 0

    if (
        booking.attendance_status == status
        and booking.extra_wait_minutes == extra_wait_minutes
    ):
        return booking

    booking.attendance_status = status
    booking.extra_wait_minutes = extra_wait_minutes
    booking.attendance_updated_at = timezone.now()

    # Visited means the appointment was completed; changing the mark away
    # from visited takes the booking back to confirmed
    booking.status = "completed" if status == "visited" else "confirmed"

    booking.save(
        update_fields=[
            "attendance_status",
            "extra_wait_minutes",
            "attendance_updated_at",
            "status",
        ]
    )

    return booking