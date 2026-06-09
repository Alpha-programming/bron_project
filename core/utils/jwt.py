import jwt

from datetime import (
    datetime,
    timedelta,
)

from django.conf import settings

from core.models import User


def create_access_token(user):

    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": datetime.utcnow() + timedelta(days=7),
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

    except jwt.ExpiredSignatureError:
        return None

    except jwt.InvalidTokenError:
        return None


def get_user_from_token(token):

    payload = decode_access_token(token)

    if not payload:
        return None

    try:

        return User.objects.get(
            id=payload["user_id"]
        )

    except User.DoesNotExist:
        return None