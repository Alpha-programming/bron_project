from ninja import Router
from core.security import JWTAuth
from core.models import User
from core.schemas.booking import (
    BookingCreateSchema,
    BookingUpdateSchema,
    BookingOutSchema,
    BookingListSchema,
)
from core.services.booking import (
    create_booking,
    get_booking,
    get_user_bookings,
    update_booking,
    delete_booking,
)

router = Router(tags=["Bookings"])


@router.post("/create", auth=JWTAuth(), response=BookingOutSchema)
def create_booking_view(request, payload: BookingCreateSchema):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_booking(user, payload)


@router.get("/my", auth=JWTAuth(), response=list[BookingListSchema])
def my_bookings(request):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return get_user_bookings(user)


@router.get("/{booking_id}", response=BookingOutSchema)
def booking_detail(request, booking_id: int):
    return get_booking(booking_id)


@router.put("/{booking_id}", auth=JWTAuth(), response=BookingOutSchema)
def update_booking_view(request, booking_id: int, payload: BookingUpdateSchema):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    booking = get_booking(booking_id)
    return update_booking(user, booking, payload)


@router.delete("/{booking_id}", auth=JWTAuth())
def delete_booking_view(request, booking_id: int):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    booking = get_booking(booking_id)
    return delete_booking(user, booking)