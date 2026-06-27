from ninja import Router
from core.security import JWTAuth
from core.schemas.business import BusinessCreateSchema, BusinessUpdateSchema, BusinessOutSchema, BusinessListSchema, BusinessStatsOutSchema
from core.services.business import get_all_businesses, get_business_by_id, create_business, update_business, delete_business
from core.models import User, Business
from core.services.business import calculate_business_metrics
from typing import List

router = Router(tags=["Business"])


@router.get("/", response=list[BusinessListSchema])
def business_list(request):
    return get_all_businesses()


@router.post("/create", auth=JWTAuth())
def create_business_view(request, payload: BusinessCreateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    business = create_business(user, payload)
    return {"message": "Business created successfully", "business_id": business.id}


# --- FIXED: MOVED UP ABOVE THE DYNAMIC ID PARAMETER ---
@router.get("/search", response=List[BusinessOutSchema])
def search_businesses(request, q: str):
    """
    Search businesses by name, description, or address match.
    """
    if not q:
        return Business.objects.all()
    return Business.objects.filter(name__icontains=q) | Business.objects.filter(description__icontains=q)


# --- FIXED: MOVED UP ABOVE THE DYNAMIC ID PARAMETER ---
@router.get("/category/{category}", response=List[BusinessOutSchema])
def filter_businesses_by_category(request, category: str):
    """
    Filter operational venues based on industry categories.
    """
    return Business.objects.filter(category__iexact=category)


@router.get("/{business_id}", response=BusinessOutSchema)
def business_detail(request, business_id: int):
    return get_business_by_id(business_id)


@router.put("/{business_id}", auth=JWTAuth())
def update_business_view(request, business_id: int, payload: BusinessUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    business = get_business_by_id(business_id)
    update_business(user, business, payload)
    return {"message": "Business updated successfully"}


@router.delete("/{business_id}", auth=JWTAuth())
def delete_business_view(request, business_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    business = get_business_by_id(business_id)
    return delete_business(user, business)


@router.get("/{business_id}/stats", auth=JWTAuth(), response=BusinessStatsOutSchema)
def get_business_statistics(request, business_id: int):
    """
    Returns data visualization stats for administrators and managers.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    return calculate_business_metrics(business_id)


@router.get("/{business_id}/analytics", auth=JWTAuth())
def get_business_analytics(request, business_id: int):
    return calculate_business_metrics(business_id)