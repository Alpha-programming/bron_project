from ninja import Router

from core.schemas.service import (
    ServiceCreateSchema,
    ServiceUpdateSchema,
    ServiceOutSchema,
    ServiceListSchema,
)

from core.services.service import (
    create_service,
    get_services,
    get_service,
    get_business_services,
    update_service,
    delete_service,
)

from core.utils.auth import (
    get_current_user,
)

router = Router(
    tags=["Services"]
)

@router.post(
    "/create",
    response=ServiceOutSchema
)
def create_service_view(
    request,
    payload: ServiceCreateSchema
):

    user = get_current_user(
        request
    )

    return create_service(
        user,
        payload
    )

@router.get(
    "/",
    response=list[ServiceListSchema]
)
def service_list(request):

    return get_services()

@router.get(
    "/{service_id}",
    response=ServiceOutSchema
)
def service_detail(
    request,
    service_id: int
):

    return get_service(
        service_id
    )

@router.get(
    "/business/{business_id}",
    response=list[ServiceListSchema]
)
def business_services(
    request,
    business_id: int
):

    return get_business_services(
        business_id
    )

@router.put(
    "/{service_id}",
    response=ServiceOutSchema
)
def update_service_view(
    request,
    service_id: int,
    payload: ServiceUpdateSchema
):

    user = get_current_user(
        request
    )

    service = get_service(
        service_id
    )

    return update_service(
        user,
        service,
        payload
    )

@router.delete(
    "/{service_id}"
)
def delete_service_view(
    request,
    service_id: int
):

    user = get_current_user(
        request
    )

    service = get_service(
        service_id
    )

    return delete_service(
        user,
        service
    )