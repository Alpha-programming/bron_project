from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Q
from ninja.errors import HttpError
from core.models import Review, Favorite, Business, User, Booking
from core.schemas.engagement import (
    ReviewCreateSchema,
    ReviewUpdateSchema,
    FavoriteCreateSchema,
    CustomerReviewCreateSchema
)

# --- REVIEW SERVICE ENGINES ---
def add_business_review(user: User, data: ReviewCreateSchema) -> Review:
    if not 1 <= data.rating <= 5:
        raise HttpError(400, "Rating must be between 1 and 5.")

    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Target business profile not found.")

    booking = None

    if data.booking_id is not None:
        try:
            booking = Booking.objects.get(
                id=data.booking_id,
                user=user,
                business=business,
            )
        except Booking.DoesNotExist:
            raise HttpError(
                404,
                "Booking for this business not found."
            )

        if booking.attendance_status != "visited":
            raise HttpError(
                400,
                "Business can only be reviewed after visiting."
            )

        if Review.objects.filter(
            booking=booking,
            review_type="business"
        ).exists():
            raise HttpError(
                400,
                "Business has already been reviewed for this booking."
            )

    return Review.objects.create(
        user=user,
        business=business,
        booking=booking,
        review_type="business",
        rating=data.rating,
        comment=data.comment,
    )

def add_customer_review(
    user: User,
    customer_id: int,
    data: CustomerReviewCreateSchema
) -> Review:

    if not 1 <= data.rating <= 5:
        raise HttpError(400, "Rating must be between 1 and 5.")

    try:
        customer = User.objects.get(
            id=customer_id,
            role="customer"
        )
    except User.DoesNotExist:
        raise HttpError(404, "Customer not found.")

    try:
        booking = Booking.objects.select_related(
            "business",
            "user"
        ).get(
            id=data.booking_id,
            user=customer
        )
    except Booking.DoesNotExist:
        raise HttpError(
            404,
            "Booking for this customer not found."
        )

    if booking.business.owner_id != user.id:
        raise HttpError(
            403,
            "Only the business owner can review this customer."
        )

    if booking.attendance_status != "visited":
        raise HttpError(
            400,
            "Customer can only be reviewed after visiting."
        )

    if Review.objects.filter(
        booking=booking,
        review_type="customer"
    ).exists():
        raise HttpError(
            400,
            "Customer has already been reviewed for this booking."
        )

    return Review.objects.create(
        user=user,
        customer=customer,
        booking=booking,
        review_type="customer",
        rating=data.rating,
        comment=data.comment
    )


def modify_user_review(user: User, review_id: int, data: ReviewUpdateSchema) -> Review:
    try:
        review = Review.objects.select_related("user").get(id=review_id)
    except Review.DoesNotExist:
        raise HttpError(404, "Review log not found.")

    if review.user != user:
        raise HttpError(403, "You do not have permission to modify this review.")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "rating" and (value < 1 or value > 5):
            raise HttpError(400, "Rating value must be set between 1 and 5.")
        setattr(review, field, value)

    review.save()
    return review


def remove_user_review(user: User, review_id: int) -> dict:
    try:
        review = Review.objects.get(id=review_id)
    except Review.DoesNotExist:
        raise HttpError(404, "Review log not found.")

    if review.user != user and not user.is_staff:
        raise HttpError(403, "Permission denied.")

    review.delete()
    return {"success": True, "message": "Review post removed successfully."}


# Score of each attendance mark in the customer's booking rating
ATTENDANCE_POINTS = {
    "visited": Decimal("5"),
    "late": Decimal("3"),
    "no_show": Decimal("2.5"),
}


def customer_booking_rating(customer: User) -> dict:
    """
    Attendance rating built from the current mark of each booking, so
    re-sending a mark or changing it never adds a second score.
    Cancelled bookings don't count. Separate from the review rating.
    """
    counts = Booking.objects.filter(
        user=customer,
        attendance_status__in=list(ATTENDANCE_POINTS),
    ).exclude(
        status__in=("cancelled", "rejected"),
    ).aggregate(**{
        mark: Count("id", filter=Q(attendance_status=mark))
        for mark in ATTENDANCE_POINTS
    })

    evaluated = sum(counts.values())
    booking_rating = None

    if evaluated:
        score = sum(ATTENDANCE_POINTS[mark] * count for mark, count in counts.items())
        booking_rating = float(
            (score / evaluated).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )

    return {
        "booking_rating": booking_rating,
        "evaluated_bookings_count": evaluated,
        "on_time_count": counts["visited"],
        "late_count": counts["late"],
        "no_show_count": counts["no_show"],
    }


# --- FAVORITE SERVICE ENGINES ---
def toggle_business_bookmark(user: User, data: FavoriteCreateSchema) -> Favorite:
    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found.")

    favorite, created = Favorite.objects.get_or_create(user=user, business=business)
    return favorite


def remove_business_bookmark(user: User, favorite_id: int) -> dict:
    try:
        favorite = Favorite.objects.get(id=favorite_id, user=user)
    except Favorite.DoesNotExist:
        raise HttpError(404, "Bookmark record not found.")

    favorite.delete()
    return {"success": True, "message": "Bookmark successfully dropped."}