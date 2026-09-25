from ninja.errors import HttpError
from core.models import Business
from core.services.category import get_category_by_id
from django.db.models import Sum
from core.models import Booking
from decimal import Decimal


def get_all_businesses():

    return Business.objects.select_related(
        "owner",
        "category",
    ).filter(is_active=True)


def get_business_by_id(
    business_id: int
):

    try:

        return Business.objects.select_related(
            "owner",
            "category",
        ).get(
            id=business_id
        )

    except Business.DoesNotExist:

        raise HttpError(
            404,
            "Business not found"
        )


def create_business(user, data):

    values = data.model_dump()

    # These model fields use blank=True but NOT null=True,
    # so PostgreSQL must receive "" instead of None.
    values["description"] = values.get("description") or ""
    values["tin"] = values.get("tin") or ""
    values["website"] = values.get("website") or ""
    values["comments"] = values.get("comments") or ""

    # Store only the networks that were actually provided
    values["social_links"] = data.social_links.model_dump(exclude_none=True)

    values["category"] = get_category_by_id(values.pop("category_id"))

    return Business.objects.create(
        owner=user,
        **values
    )


def update_business(user, business, data):

    if business.owner != user:
        raise HttpError(
            403,
            "Permission denied"
        )

    values = data.model_dump(exclude_unset=True)

    if values.get("category_id") is not None:
        values["category"] = get_category_by_id(values.pop("category_id"))
    else:
        values.pop("category_id", None)

    non_nullable_text_fields = {
        "description",
        "tin",
        "website",
        "comments",
        "email",
        "owner_name",
    }

    for field, value in values.items():

        if field in non_nullable_text_fields and value is None:
            value = ""

        if field == "social_links":
            # Replace the whole set; None clears it
            value = data.social_links.model_dump(exclude_none=True) if data.social_links else {}

        setattr(
            business,
            field,
            value
        )

    business.save()

    return business


def delete_business(
    user,
    business,
):

    if business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    business.delete()

    return {
        "message": "Business deleted successfully"
    }


def calculate_business_metrics(business_id: int) -> dict:
    bookings_qs = Booking.objects.filter(business_id=business_id)

    total_bookings = bookings_qs.count()
    pending_bookings = bookings_qs.filter(status="pending").count()  # Note: Match model choice lowercase standard
    approved_bookings = bookings_qs.filter(status="confirmed").count()  # Match model choice lowercase standard
    cancelled_bookings = bookings_qs.filter(status="cancelled").count()  # Match model choice lowercase standard

    revenue_sum = bookings_qs.exclude(status="cancelled").aggregate(total=Sum('total_price'))['total'] or Decimal(
        '0.00')

    return {
        "total_bookings": total_bookings,
        "pending_bookings": pending_bookings,
        "approved_bookings": approved_bookings,
        "cancelled_bookings": cancelled_bookings,
        "total_revenue": str(revenue_sum)  # Standardizing as safe string across JSON limits or Decimal types
    }