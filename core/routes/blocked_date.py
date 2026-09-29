# Aliased so the `date` query parameter below can keep its public name
from datetime import date as date_type
from ninja import Router, Query
from core.security import JWTAuth
from core.models import User
from core.schemas.blocked_date import (
    BlockedDateCreateSchema,
    BlockedDateUpdateSchema,
    BlockedDateOutSchema,
    BlockedCheckOutSchema,  # New
)
from core.services.blocked_date import (
    create_blocked_date,
    get_business_blocked_dates,
    get_blocked_date,
    update_blocked_date,
    delete_blocked_date,
    check_date_blockage,  # New
)

router = Router(tags=["Blocked Dates"])


@router.post("/create", auth=JWTAuth(), response=BlockedDateOutSchema)
def create_blocked_date_view(request, payload: BlockedDateCreateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_blocked_date(user, payload)


@router.get("/business/{business_id}", response=list[BlockedDateOutSchema])
def business_blocked_dates(request, business_id: int):
    return get_business_blocked_dates(business_id)


@router.get(
    "/check",
    response={200: BlockedCheckOutSchema},
    summary="Check whether a date is blocked",
)
def check_blocked_date_view(
    request,
    business_id: int = Query(..., description="Business ID"),
    date: date_type = Query(..., description="Date to check, YYYY-MM-DD"),
):
    """
    Tells whether the business has blocked bookings on the given date.

    Auth: none (public). Query parameters: `business_id` and `date` (YYYY-MM-DD),
    both required; the old `target_date` parameter is not accepted.
    An unknown business is not an error: the response has `is_blocked: false`.
    `reason` is null when the date is not blocked or the business gave no reason.

    Errors: 422 - `business_id` or `date` is missing or malformed.
    """
    return check_date_blockage(business_id, date)


# Keep your detail, update, and delete paths exactly as they are at the bottom
@router.get("/{blocked_date_id}", response=BlockedDateOutSchema)
def blocked_date_detail(request, blocked_date_id: int):
    return get_blocked_date(blocked_date_id)


@router.put("/{blocked_date_id}", auth=JWTAuth(), response=BlockedDateOutSchema)
def update_blocked_date_view(request, blocked_date_id: int, payload: BlockedDateUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    blocked_date = get_blocked_date(blocked_date_id)
    return update_blocked_date(user, blocked_date, payload)


@router.delete("/{blocked_date_id}", auth=JWTAuth())
def delete_blocked_date_view(request, blocked_date_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    blocked_date = get_blocked_date(blocked_date_id)
    return delete_blocked_date(user, blocked_date)