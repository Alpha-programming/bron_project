from ninja import Router
from core.security import JWTAuth
from core.models import User, Service
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
    get_distinct_service_categories,
)
from typing import List

router = Router(tags=["Services"])


@router.post("/create", auth=JWTAuth(), response=ServiceOutSchema)
def create_service_view(request, payload: ServiceCreateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_service(user, payload)


@router.get("/", response=list[ServiceListSchema])
def service_list(request):
    return get_services()


@router.get("/categories", response=List[str])
def service_categories_view(request):
    """
    Fetches a unique list of all service categories to build filtering menus.
    """
    return get_distinct_service_categories()


# --- FIXED: MOVED ABOVE THE DYNAMIC ID PATHS & FILTER CHANGED TO TITLE ---
@router.get("/search", response=List[ServiceOutSchema])
def search_services(request, q: str):
    """
    Find services matching text constraints.
    """
    return Service.objects.filter(title__icontains=q)


@router.get("/business/{business_id}", response=list[ServiceListSchema])
def business_services(request, business_id: int):
    return get_business_services(business_id)


@router.get("/{service_id}", response=ServiceOutSchema)
def service_detail(request, service_id: int):
    return get_service(service_id)


@router.put("/{service_id}", auth=JWTAuth(), response=ServiceOutSchema)
def update_service_view(request, service_id: int, payload: ServiceUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    service = get_service(service_id)
    return update_service(user, service, payload)


@router.delete("/{service_id}", auth=JWTAuth())
def delete_service_view(request, service_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    service = get_service(service_id)
    return delete_service(user, service)