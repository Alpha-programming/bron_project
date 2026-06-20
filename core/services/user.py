import uuid
from django.utils import timezone
from datetime import timedelta
from ninja.errors import HttpError
from core.models import User, TelegramLinkToken


def create_tg_token(user):
    """
    Generates a secure 10-minute one-time link token for Telegram pairing.
    """
    # Clean up old active tokens for this user
    TelegramLinkToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate a unique secure token string
    token_str = str(uuid.uuid4().hex)[:16]
    expiry = timezone.now() + timedelta(minutes=10)

    TelegramLinkToken.objects.create(
        user=user,
        token=token_str,
        expires_at=expiry,
        is_used=False
    )

    return token_str


def update_profile(user, data):
    """
    Updates user profile parameters and validates uniqueness constraints.
    """
    # Read fields passed explicitly in the JSON payload
    payload_dict = data.model_dump(exclude_unset=True)

    if "telegram_id" in payload_dict and payload_dict["telegram_id"] is not None:
        tg_id = payload_dict["telegram_id"]

        # Verify no other profile has claimed this Telegram ID
        if User.objects.filter(telegram_id=tg_id).exclude(id=user.id).exists():
            raise HttpError(400, "This Telegram account is already linked to another profile.")

    for field, value in payload_dict.items():
        setattr(user, field, value)

    user.save()
    return user