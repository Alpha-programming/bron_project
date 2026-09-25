from ninja.errors import HttpError

from core.utils.jwt import decode_access_token


def get_current_user(request):
    """
    Safely retrieves the authenticated user already resolved by JWTAuth.
    """
    # Ninja stores the result of JWTAuth.authenticate in request.auth,
    # request.user stays AnonymousUser for bearer-token requests
    user = getattr(request, "auth", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user

    # Fallback for manually called contexts or route misconfigurations
    raise HttpError(401, "User is not authenticated or token is missing.")


def get_optional_user(request):
    """
    For public endpoints that behave differently for logged-in users:
    returns the User from a Bearer token if one is present and valid, else None.
    """
    from core.models import User

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None

    payload = decode_access_token(header[len("Bearer "):].strip())
    if not payload:
        return None

    return User.objects.filter(id=payload.get("user_id")).first()
