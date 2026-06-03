from ninja import Router

from core.schemas.user import (
    UserProfileOutSchema,
    UserProfileUpdateSchema,
)

from core.services.user import (
    update_profile,
)

from core.utils.auth import (
    get_current_user,
)

router = Router(tags=["Users"])


@router.get(
    "/profile",
    response=UserProfileOutSchema
)
def profile(request):

    return get_current_user(request)


@router.put(
    "/profile",
    response=UserProfileOutSchema
)
def update_user_profile(
    request,
    payload: UserProfileUpdateSchema,
):

    user = get_current_user(request)

    return update_profile(
        user,
        payload,
    )