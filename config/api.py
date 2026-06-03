from ninja import NinjaAPI

from core.routes.auth import router as auth_router
from core.routes.user import router as user_router

api = NinjaAPI(
    title="Iron API",
    version="1.0.0",
)

api.add_router(
    "/auth/",
    auth_router
)

api.add_router(
    "/users/",
    user_router
)


@api.get("/")
def root(request):
    return {
        "message": "Iron API is running"
    }