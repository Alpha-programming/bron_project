from ninja import Router
from core.security import JWTAuth
from core.models import User
from core.schemas.working_hours import (
    WorkingHoursCreateSchema,
    WorkingHoursUpdateSchema,
    WorkingHoursOutSchema,
    TodayScheduleOutSchema,  # New
)
from core.services.working_hours import (
    create_working_hours,
    get_business_schedule,
    get_working_hours,
    update_working_hours,
    delete_working_hours,
    get_today_business_schedule,  # New
)

router = Router(tags=["Working Hours"])


@router.post("/create", auth=JWTAuth(), response=WorkingHoursOutSchema)
def create_schedule(request, payload: WorkingHoursCreateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_working_hours(user, payload)


@router.get("/business/{business_id}", response=list[WorkingHoursOutSchema])
def business_schedule(request, business_id: int):
    return get_business_schedule(business_id)


# --- NEW EXPANSION ENDPOINT ---

@router.get("/today/{business_id}", response=TodayScheduleOutSchema)
def working_hours_today_view(request, business_id: int):
    """
    Fetches the running operating schedule hours mapping for the current calendar date.
    """
    return get_today_business_schedule(business_id)


# Keep your detail, update, and delete paths exactly as they are at the bottom
@router.get("/{working_hours_id}", response=WorkingHoursOutSchema)
def working_hours_detail(request, working_hours_id: int):
    return get_working_hours(working_hours_id)


@router.put("/{working_hours_id}", auth=JWTAuth(), response=WorkingHoursOutSchema)
def update_schedule(request, working_hours_id: int, payload: WorkingHoursUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    working_hours = get_working_hours(working_hours_id)
    return update_working_hours(user, working_hours, payload)


@router.delete("/{working_hours_id}", auth=JWTAuth())
def delete_schedule(request, working_hours_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    working_hours = get_working_hours(working_hours_id)
    return delete_working_hours(user, working_hours)