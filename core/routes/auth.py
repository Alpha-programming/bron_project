from ninja import Router
from core.security import JWTAuth
from core.schemas.auth import RegisterSchema, LoginSchema, LoginResponseSchema, UserOutSchema
from core.services.auth import register_user, login_user
from core.models import User
from ninja.errors import HttpError

router = Router(tags=["Authentication"])


@router.post("/register")
def register(request, payload: RegisterSchema):
    try:
        user = register_user(payload)
        return {"message": "User created successfully", "user_id": user.id}
    except HttpError as e:
        return {"message": "User already registered, proceeding to login.", "user_id": None}


@router.post("/login", response=LoginResponseSchema)
def login(request, payload: LoginSchema):
    return login_user(payload)


@router.get("/me", auth=JWTAuth(), response=UserOutSchema)
def me(request):
    # 1. Django Ninja places the authenticated model instance inside request.auth
    user = request.auth

    # 2. If it's wrapped or missing, fallback to looking it up directly by id
    if not user or hasattr(user, '_wrapped'):
        user_id = getattr(request.auth, 'id', None) or getattr(request.user, 'id', None)
        if user_id:
            user = User.objects.get(id=user_id)
        else:
            raise HttpError(401, "Invalid or unreadable authentication token identity.")

    # 3. Apply default role fallback if missing
    if not getattr(user, 'role', None):
        user.role = "client"

    return user