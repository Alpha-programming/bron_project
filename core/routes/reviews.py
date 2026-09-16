from typing import List

from ninja import Router
from ninja.errors import HttpError

from core.security import JWTAuth
from core.models import Review, User

from core.schemas.engagement import (
    ReviewOutSchema,
    ReviewCreateSchema,
    CustomerReviewCreateSchema,
    ReviewUpdateSchema,
    CustomerRatingSchema,
)

from core.services.engagement import (
    add_business_review,
    add_customer_review,
    modify_user_review,
    remove_user_review,
)
router = Router(tags=["Reviews & Ratings"])

@router.post("/", auth=JWTAuth(), response=ReviewOutSchema)
def create_review_view(request, payload: ReviewCreateSchema):
    """
    Submits a user rating evaluation score text block to a merchant.
    """
    return add_business_review(request.auth, payload)


@router.get("/business/{business_id}", response=List[ReviewOutSchema])
def get_business_reviews_view(request, business_id: int):
    """
    Fetches the running public evaluation ledger history logs.
    """
    return Review.objects.filter(business_id=business_id).select_related("user")

@router.post(
    "/customer/{customer_id}",
    auth=JWTAuth(),
    response=ReviewOutSchema
)
def create_customer_review_view(
    request,
    customer_id: int,
    payload: CustomerReviewCreateSchema
):
    return add_customer_review(
        request.auth,
        customer_id,
        payload
    )


@router.get(
    "/customer/{customer_id}",
    response=List[ReviewOutSchema]
)
def get_customer_reviews_view(
    request,
    customer_id: int
):
    return Review.objects.filter(
        customer_id=customer_id,
        review_type="customer"
    ).select_related(
        "user",
        "customer"
    )


@router.get(
    "/customer/{customer_id}/rating",
    response=CustomerRatingSchema
)
def get_customer_rating_view(
    request,
    customer_id: int
):
    try:
        customer = User.objects.get(
            id=customer_id,
            role="customer"
        )
    except User.DoesNotExist:
        raise HttpError(404, "Customer not found.")

    return {
        "user_id": customer.id,
        "username": customer.username,
        "rating": customer.rating,
        "reviews_count": customer.reviews_count,
    }

@router.put("/{id}", auth=JWTAuth(), response=ReviewOutSchema)
def update_review_view(request, id: int, payload: ReviewUpdateSchema):
    """
    Updates an existing feedback post written by the current account holder.
    """
    return modify_user_review(request.auth, id, payload)


@router.delete("/{id}", auth=JWTAuth())
def delete_review_view(request, id: int):
    """
    Removes a review log trace completely.
    """
    return remove_user_review(request.auth, id)