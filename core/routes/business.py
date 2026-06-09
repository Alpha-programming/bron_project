from ninja import Router

from core.schemas.business import (
    BusinessCreateSchema,
    BusinessUpdateSchema,
    BusinessOutSchema,
    BusinessListSchema,
)

from core.services.business import (
    get_all_businesses,
    get_business_by_id,
    create_business,
    update_business,
    delete_business,
)

from core.utils.auth import (
    get_current_user
)

router = Router(
    tags=["Business"]
)

@router.get(
    "/",
    response=list[BusinessListSchema]
)
def business_list(request):

    businesses = get_all_businesses()

    result = []

    for business in businesses:

        result.append(
            {
                "id": business.id,
                "name": business.name,
                "category": business.category,
                "address": business.address,
                "phone": business.phone,
                "logo": (
                    business.logo.url
                    if business.logo
                    else None
                ),
            }
        )

    return result

@router.get(
    "/{business_id}",
    response=BusinessOutSchema
)
def business_detail(
    request,
    business_id: int
):

    business = get_business_by_id(
        business_id
    )

    return {
        "id": business.id,

        "owner_id": business.owner.id,
        "owner_username": business.owner.username,

        "name": business.name,
        "description": business.description,

        "logo": (
            business.logo.url
            if business.logo
            else None
        ),

        "category": business.category,

        "address": business.address,
        "phone": business.phone,

        "latitude": business.latitude,
        "longitude": business.longitude,

        "created_at": str(
            business.created_at
        ),
    }

@router.post(
    "/create"
)
def create_business_view(
    request,
    payload: BusinessCreateSchema
):

    user = get_current_user(
        request
    )

    business = create_business(
        user,
        payload
    )

    return {
        "message": "Business created successfully",
        "business_id": business.id,
    }

@router.put(
    "/{business_id}"
)
def update_business_view(
    request,
    business_id: int,
    payload: BusinessUpdateSchema
):

    user = get_current_user(
        request
    )

    business = get_business_by_id(
        business_id
    )

    update_business(
        user,
        business,
        payload
    )

    return {
        "message": "Business updated successfully"
    }

@router.delete(
    "/{business_id}"
)
def delete_business_view(
    request,
    business_id: int
):

    user = get_current_user(
        request
    )

    business = get_business_by_id(
        business_id
    )

    return delete_business(
        user,
        business
    )