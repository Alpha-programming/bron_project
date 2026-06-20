from ninja import Router
from core.security import JWTAuth
from core.schemas.business import BusinessCreateSchema, BusinessUpdateSchema, BusinessOutSchema, BusinessListSchema
from core.services.business import get_all_businesses, get_business_by_id, create_business, update_business, delete_business
from core.models import User

router = Router(tags=["Business"])

@router.get("/", response=list[BusinessListSchema])
def business_list(request):
    return get_all_businesses()

@router.post("/create", auth=JWTAuth())
def create_business_view(request, payload: BusinessCreateSchema):
    # FIX: Use request.auth (falls back to direct lookup if wrapped)
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    business = create_business(user, payload)
    return {"message": "Business created successfully", "business_id": business.id}


# Inside core/routes/businesses.py
@router.get("/{business_id}", response=BusinessOutSchema)
def business_detail(request, business_id: int):
    return get_business_by_id(business_id)

@router.put("/{business_id}", auth=JWTAuth())
def update_business_view(request, business_id: int, payload: BusinessUpdateSchema):
    # FIX: Use request.auth to prevent lazy-loading permission denial crashes
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    business = get_business_by_id(business_id)
    update_business(user, business, payload)
    return {"message": "Business updated successfully"}

@router.delete("/{business_id}", auth=JWTAuth())
def delete_business_view(request, business_id: int):
    # FIX: Use request.auth for clean permission tracking
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    business = get_business_by_id(business_id)
    return delete_business(user, business)