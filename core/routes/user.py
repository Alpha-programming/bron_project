from ninja import Router
from core.security import JWTAuth
from core.schemas.user import (
    UserProfileOutSchema,
    UserProfileUpdateSchema,
    PhoneTgSchema,
    ChangePasswordSchema  # New
)
from core.schemas.auth import LoginResponseSchema
from core.services.user import (
    update_profile,
    create_tg_token,
    change_user_password,  # New
    execute_profile_deletion  # New
)
from core.models import User
from ninja.errors import HttpError
from core.utils.jwt import create_access_token

router = Router(tags=["Users"])


@router.get("/profile", auth=JWTAuth(), response=UserProfileOutSchema)
def get_user_profile(request):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return user


@router.put("/profile", auth=JWTAuth(), response=UserProfileOutSchema)
def update_user_profile(request, payload: UserProfileUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return update_profile(user, payload)


@router.post("/telegram/connect", response=LoginResponseSchema)
def one_time_telegram_token(request, payload: PhoneTgSchema):
    try:
        user = User.objects.get(phone=payload.phone)
    except User.DoesNotExist:
        raise HttpError(404, "User with this phone number does not exist.")

    token = create_access_token(user)
    return {
        "access_token": token,
        "user_id": user.id,
        "username": user.username,
        "tg_token": None
    }


@router.put("/profile/telegram", auth=JWTAuth(), response=UserProfileOutSchema)
def update_user_telegram_id(request, payload: UserProfileUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return update_profile(user, payload)


# --- NEW EXPANSION ENDPOINTS ---

@router.post("/change-password", auth=JWTAuth())
def change_password_view(request, payload: ChangePasswordSchema):
    """
    Securely updates the authenticated user's account password.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    change_user_password(user, payload)
    return {"message": "Password updated successfully."}


@router.delete("/profile", auth=JWTAuth())
def delete_profile_view(request):
    """
    Permanently deletes the active user's profile account from the ecosystem.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    return execute_profile_deletion(user)