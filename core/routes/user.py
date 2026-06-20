from ninja import Router
from core.security import JWTAuth
from core.schemas.user import UserProfileOutSchema, UserProfileUpdateSchema, PhoneTgSchema
from core.schemas.auth import LoginResponseSchema
from core.services.user import update_profile, create_tg_token
from core.models import User
from ninja.errors import HttpError
from core.utils.jwt import create_access_token

router = Router(tags=["Users"])


@router.get("/profile", auth=JWTAuth(), response=UserProfileOutSchema)
def get_user_profile(request):
    """
    Fetches the authenticated user profile details.
    """
    # FIX: Read from request.auth instead of request.user
    user = request.auth

    # Fallback if the user instance is wrapped by lazy-loading middleware
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    return user


@router.put("/profile", auth=JWTAuth(), response=UserProfileOutSchema)
def update_user_profile(request, payload: UserProfileUpdateSchema):
    """
    Updates the authenticated user profile details.
    """
    # FIX: Read from request.auth instead of request.user
    user = request.auth

    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    # Pass the clean user instance to your update logic
    return update_profile(user, payload)

@router.post("/telegram/connect")
def telegram_connect(request, payload: PhoneTgSchema):
    try:
        user = User.objects.get(phone=payload.phone)
    except User.DoesNotExist:
        raise HttpError(404, "User not found")

    token = create_access_token(user)
    return {
        "access_token": token,
        "user_id": user.id,
        "username": user.username,
    }


@router.post("/telegram/connect", response=LoginResponseSchema)
def one_time_telegram_token(request, payload: PhoneTgSchema):
    """
    Generates a system authentication token via phone check for Telegram linking.
    """
    try:
        user = User.objects.get(phone=payload.phone)
    except User.DoesNotExist:
        # Instead of returning None (which breaks response schemas), raise a proper HTTP 404
        raise HttpError(404, "User with this phone number does not exist.")

    token = create_tg_token(user)

    return {
        "access_token": token,
        "user_id": user.id,
        "username": user.username,
    }


@router.put("/profile/telegram", auth=JWTAuth(), response=UserProfileOutSchema)
def update_user_telegram_id(request, payload: UserProfileUpdateSchema):
    """
    Securely updates the authenticated user's Telegram ID.
    """
    # Simply extract the user directly from the secure request object!
    return update_profile(request.user, payload)