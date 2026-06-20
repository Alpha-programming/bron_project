import jwt
from django.utils import timezone
from datetime import timedelta
from django.conf import settings


def create_access_token(user):
    # Use Django's native timezone tracking configuration
    expiration = timezone.now() + timedelta(days=7)

    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": int(expiration.timestamp()),  # JWT specification requires integer UNIX timestamps
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def decode_access_token(token):
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None