from ninja import Router

from core.schemas.business_application import (
    BusinessApplicationCreateSchema,
    BusinessApplicationOutSchema,
)
from core.services.business_application import create_business_application
from core.utils.auth import get_optional_user
from core.utils.helpers import get_client_ip

router = Router(tags=["Business applications"])


@router.post("/create", response={201: BusinessApplicationOutSchema})
def submit_business_application(request, payload: BusinessApplicationCreateSchema):
    """
    "Register your business" form: full name and phone are required,
    email, Instagram/Telegram and comment are optional. No category or address.
    Public; a Bearer token, if sent, links the application to the user.
    Applications are reviewed in the admin panel.
    """
    application = create_business_application(
        payload,
        get_optional_user(request),
        get_client_ip(request),
    )

    return 201, application
