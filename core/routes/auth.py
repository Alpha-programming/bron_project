from ninja import Router

from core.schemas.auth import (
    RegisterSchema,
    LoginSchema,
    LoginResponseSchema,
    UserOutSchema,
)

from core.services.auth import (
    register_user,
    login_user,
)

from core.utils.auth import (
    get_current_user,
)

router = Router(tags=["Authentication"])


@router.post("/register")
def register(request, payload: RegisterSchema):

    user = register_user(payload)

    return {
        "message": "User created successfully",
        "user_id": user.id,
    }


@router.post(
    "/login",
    response=LoginResponseSchema
)
def login(request, payload: LoginSchema):

    return login_user(payload)


@router.get(
    "/me",
    response=UserOutSchema
)
def me(request):

    return get_current_user(request)