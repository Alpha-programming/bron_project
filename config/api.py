from ninja import NinjaAPI

from core.routes.auth import router as auth_router
from core.routes.user import router as user_router
from core.routes.business import router as business_router
from core.routes.service import router as service_router
from core.routes.product import router as product_router
from core.routes.branch import router as branch_router
from core.routes.staff import router as staff_router
from core.routes.working_hours import router as working_hours_router
from core.routes.blocked_date import router as blocked_date_router
from core.routes.booking import router as booking_router
from core.routes.reviews import router as reviews_router
from core.routes.favorites import router as favorites_router
from core.routes.business_gallery import router as business_gallery_router
from core.routes.business_logo import router as business_logo_router

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

api.add_router(
    "/businesses/",
    business_router
)

api.add_router(
    "/services/",
    service_router
)

api.add_router(
    "/products/",
    product_router
)

api.add_router(
    "/branches/",
    branch_router
)

api.add_router(
    "/staff/",
    staff_router
)

api.add_router(
    "/working-hours/",
    working_hours_router
)

api.add_router(
    "/blocked-dates/",
    blocked_date_router
)

api.add_router(
    "/bookings/",
    booking_router
)

api.add_router(
    "/business-gallery/",
    business_gallery_router
)

api.add_router(
    "/businesses/",
    business_logo_router
)

api.add_router("/reviews", reviews_router)

api.add_router("/favorites", favorites_router)

@api.get("/")
def root(request):
    return {
        "message": "Iron API is running"
    }