from decimal import Decimal

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