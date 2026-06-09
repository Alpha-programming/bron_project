from ninja import Router

from core.schemas.blocked_date import (
    BlockedDateCreateSchema,
    BlockedDateUpdateSchema,
    BlockedDateOutSchema,
)

from core.services.blocked_date import (
    create_blocked_date,
    get_business_blocked_dates,
    get_blocked_date,
    update_blocked_date,
    delete_blocked_date,
)

from core.utils.auth import (
    get_current_user
)

router = Router(tags=["Blocked Dates"])

@router.post(
    "/create",
    response=BlockedDateOutSchema
)
def create_blocked_date_view(
    request,
    payload: BlockedDateCreateSchema
):

    user = get_current_user(
        request
    )

    return create_blocked_date(
        user,
        payload
    )

@router.get(
    "/business/{business_id}",
    response=list[BlockedDateOutSchema]
)
def business_blocked_dates(
    request,
    business_id: int
):

    return get_business_blocked_dates(
        business_id
    )

@router.get(
    "/{blocked_date_id}",
    response=BlockedDateOutSchema
)
def blocked_date_detail(
    request,
    blocked_date_id: int
):

    return get_blocked_date(
        blocked_date_id
    )

@router.put(
    "/{blocked_date_id}",
    response=BlockedDateOutSchema
)
def update_blocked_date_view(
    request,
    blocked_date_id: int,
    payload: BlockedDateUpdateSchema
):

    user = get_current_user(
        request
    )

    blocked_date = get_blocked_date(
        blocked_date_id
    )

    return update_blocked_date(
        user,
        blocked_date,
        payload
    )

@router.delete(
    "/{blocked_date_id}"
)
def delete_blocked_date_view(
    request,
    blocked_date_id: int
):

    user = get_current_user(
        request
    )

    blocked_date = get_blocked_date(
        blocked_date_id
    )

    return delete_blocked_date(
        user,
        blocked_date
    )