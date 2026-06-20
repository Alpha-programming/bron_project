from ninja.errors import HttpError


def get_current_user(request):
    """
    Safely retrieves the authenticated user already resolved by JWTAuth.
    """
    if hasattr(request, "user") and request.user.is_authenticated:
        return request.user

    # Fallback for manually called contexts or route misconfigurations
    raise HttpError(401, "User is not authenticated or token is missing.")