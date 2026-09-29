from ninja import Router, File
from ninja.files import UploadedFile
from core.security import JWTAuth, TelegramBotAuth
from core.schemas.user import (
    UserProfileOutSchema,
    UserProfileUpdateSchema,
    PhoneTgSchema,
    ChangePasswordSchema,  # New
    NotificationSettingsSchema,
    NotificationSettingsUpdateSchema,
)
from core.schemas.auth import LoginResponseSchema
from core.schemas.common import ErrorSchema
from core.services.user import (
    update_profile,
    create_tg_token,
    upload_avatar,
    delete_avatar,
    change_user_password,  # New
    execute_profile_deletion,  # New
    get_notification_settings,
    update_notification_settings,
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


@router.post("/profile/avatar", auth=JWTAuth(), response=UserProfileOutSchema)
def upload_user_avatar(request, image: UploadedFile = File(...)):
    return upload_avatar(request.auth, image)


@router.delete("/profile/avatar", auth=JWTAuth(), response=UserProfileOutSchema)
def delete_user_avatar(request):
    return delete_avatar(request.auth)


@router.get(
    "/profile/notifications",
    auth=JWTAuth(),
    response={200: NotificationSettingsSchema, 401: ErrorSchema},
    summary="Get notification settings",
)
def get_notification_settings_view(request):
    """
    Returns the current user's notification preferences.

    Auth: JWT (Bearer token). Keys: `push`, `email`, `bookingReminder`, `promotions`.
    Defaults for a new account: `push`, `email` and `bookingReminder` are on,
    `promotions` is off (marketing is opt-in).

    Errors: 401 - missing or invalid token.
    """
    return get_notification_settings(request.auth)


@router.put(
    "/profile/notifications",
    auth=JWTAuth(),
    response={200: NotificationSettingsSchema, 401: ErrorSchema},
    summary="Update notification settings",
)
def update_notification_settings_view(request, payload: NotificationSettingsUpdateSchema):
    """
    Updates the current user's notification preferences and returns the full settings object.

    Auth: JWT (Bearer token). Partial update: send only the keys to change
    (`push`, `email`, `bookingReminder`, `promotions`); keys that are omitted
    or `null` keep their current value, unknown keys are ignored.

    Errors: 401 - missing or invalid token; 422 - a value is not a valid boolean.
    """
    return update_notification_settings(request.auth, payload)


@router.post("/telegram/connect", auth=TelegramBotAuth(), response=LoginResponseSchema)
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