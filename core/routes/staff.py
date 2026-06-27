from ninja import Router
from core.security import JWTAuth
from core.models import User, Staff
from core.schemas.staff import (
    StaffCreateSchema,
    StaffUpdateSchema,
    StaffListSchema,
    StaffOutSchema,
    StaffScheduleOutSchema,  # New
)
from core.schemas.booking import BookingOutSchema  # New
from core.services.staff import (
    create_staff,
    get_staff_list,
    get_staff,
    get_business_staff,
    update_staff,
    delete_staff,
    get_staff_schedule_timeline,  # New
    get_staff_assigned_bookings,  # New
)
from typing import List

router = Router(tags=["Staff"])


@router.post("/create", auth=JWTAuth(), response=StaffOutSchema)
def create_staff_view(request, payload: StaffCreateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_staff(user, payload)


@router.get("/", response=list[StaffListSchema])
def staff_list(request):
    return get_staff_list()


@router.get("/business/{business_id}", response=list[StaffListSchema])
def business_staff(request, business_id: int):
    return get_business_staff(business_id)


# --- NEW EXPANSION ENDPOINTS ---

@router.get("/{staff_id}/schedule", response=StaffScheduleOutSchema)
def staff_schedule_view(request, staff_id: int):
    """
    Fetches the full week calendar configuration timeline for an individual provider.
    """
    staff = get_staff(staff_id)
    return get_staff_schedule_timeline(staff)


@router.get("/{staff_id}/bookings", response=List[BookingOutSchema])
def staff_bookings_view(request, staff_id: int):
    """
    Fetches all client reservations booked under this individual staff provider.
    """
    staff = get_staff(staff_id)
    return get_staff_assigned_bookings(staff)


# Keep your individual update and delete profiles exactly as they are at the bottom
@router.get("/{staff_id}", response=StaffOutSchema)
def staff_detail(request, staff_id: int):
    return get_staff(staff_id)


@router.put("/{staff_id}", auth=JWTAuth(), response=StaffOutSchema)
def update_staff_view(request, staff_id: int, payload: StaffUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    staff = get_staff(staff_id)
    return update_staff(user, staff, payload)


@router.delete("/{staff_id}", auth=JWTAuth())
def delete_staff_view(request, staff_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    staff = get_staff(staff_id)
    return delete_staff(user, staff)