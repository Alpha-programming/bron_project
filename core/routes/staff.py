from ninja import Router
from core.security import JWTAuth
from core.models import User
from core.schemas.staff import (
    StaffCreateSchema,
    StaffUpdateSchema,
    StaffListSchema,
    StaffOutSchema,
)
from core.services.staff import (
    create_staff,
    get_staff_list,
    get_staff,
    get_business_staff,
    update_staff,
    delete_staff,
)

router = Router(tags=["Staff"])


@router.post("/create", auth=JWTAuth(), response=StaffOutSchema)
def create_staff_view(request, payload: StaffCreateSchema):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_staff(user, payload)


@router.get("/", response=list[StaffListSchema])
def staff_list(request):
    return get_staff_list()


@router.get("/{staff_id}", response=StaffOutSchema)
def staff_detail(request, staff_id: int):
    return get_staff(staff_id)


@router.get("/business/{business_id}", response=list[StaffListSchema])
def business_staff(request, business_id: int):
    return get_business_staff(business_id)


@router.put("/{staff_id}", auth=JWTAuth(), response=StaffOutSchema)
def update_staff_view(request, staff_id: int, payload: StaffUpdateSchema):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    staff = get_staff(staff_id)
    return update_staff(user, staff, payload)


@router.delete("/{staff_id}", auth=JWTAuth())
def delete_staff_view(request, staff_id: int):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    staff = get_staff(staff_id)
    return delete_staff(user, staff)