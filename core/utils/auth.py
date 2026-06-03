from ninja.errors import HttpError

from core.utils.jwt import get_user_from_token


def get_current_user(request):

    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HttpError(
            401,
            "Authorization token required"
        )

    if not auth_header.startswith("Bearer "):
        raise HttpError(
            401,
            "Invalid authorization format. Use Bearer <token>"
        )

    token = auth_header.replace(
        "Bearer ",
        ""
    )

    user = get_user_from_token(token)

    if not user:
        raise HttpError(
            401,
            "Invalid or expired token"
        )

    return user