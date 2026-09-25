from ninja.errors import HttpError


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