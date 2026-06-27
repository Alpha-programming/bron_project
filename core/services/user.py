import uuid
from datetime import timedelta
from django.utils import timezone
from ninja.errors import HttpError
from core.models import User, TelegramLinkToken
from django.contrib.auth import update_session_auth_hash

def create_tg_token(user) -> str:
    """
    Generates a secure 10-minute one-time link token for Telegram pairing.
    Deactivates any previous unused tokens for the user to maintain security.
    """
    # Clean up and invalidate old active tokens for this user
    TelegramLinkToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate a unique secure 16-character token string
    token_str = str(uuid.uuid4().hex)[:16]
    expiry = timezone.now() + timedelta(minutes=10)

    TelegramLinkToken.objects.create(
        user=user,
        token=token_str,
        expires_at=expiry,
        is_used=False
    )

    return token_str


def update_profile(user: User, data) -> User:
    """
    Updates user profile parameters dynamically and validates uniqueness constraints.
    Expects a Ninja/Pydantic Schema object for the 'data' parameter.
    """
    # Extract only the fields that were explicitly sent in the payload request
    payload_dict = data.model_dump(exclude_unset=True)

    # Enforce unique constraint check on Telegram IDs across accounts
    if "telegram_id" in payload_dict and payload_dict["telegram_id"] is not None:
        tg_id = payload_dict["telegram_id"]

        # Verify no other user profile has already claimed this Telegram registration ID
        if User.objects.filter(telegram_id=tg_id).exclude(id=user.id).exists():
            raise HttpError(400, "This Telegram account is already linked to another profile.")

    # Dynamically map payload fields directly onto the User model record properties
    for field, value in payload_dict.items():
        setattr(user, field, value)

    user.save()
    return user


def change_user_password(user: User, data) -> None:
    """
    Validates and overrides the active user credentials safely.
    """
    if not user.check_password(data.old_password):
        raise HttpError(400, "Incorrect old password provided.")

    if data.old_password == data.new_password:
        raise HttpError(400, "Your new password cannot match your current one.")

    user.set_password(data.new_password)
    user.save()


def execute_profile_deletion(user: User) -> dict:
    """
    Deletes the current user profile account records entirely.
    """
    user.delete()
    return {"success": True, "message": "Profile account successfully removed."}