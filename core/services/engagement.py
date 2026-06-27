from ninja.errors import HttpError
from core.models import Review, Favorite, Business, User
from core.schemas.engagement import (
    ReviewCreateSchema,
    ReviewUpdateSchema,
    FavoriteCreateSchema
)

# --- REVIEW SERVICE ENGINES ---
def add_business_review(user: User, data: ReviewCreateSchema) -> Review:
    if data.rating < 1 or data.rating > 5:
        raise HttpError(400, "Rating value must be set between 1 and 5.")

    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Target business profile not found.")

    return Review.objects.create(
        user=user,
        business=business,
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