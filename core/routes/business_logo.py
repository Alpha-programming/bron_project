from ninja import Router, File
from ninja.files import UploadedFile

from core.security import JWTAuth

from core.schemas.business_logo import (
    BusinessLogoOutSchema,
)

from core.services.business_logo import (
    upload_logo,
    delete_logo,
)

from core.utils.auth import (
    get_current_user,
)

router = Router(tags=["Business Logo"])


@router.post(
    "/{business_id}/logo",
    auth=JWTAuth(),
    response=BusinessLogoOutSchema,
)
def upload_business_logo(
    request,
    business_id: int,
    image: UploadedFile = File(...),
):

    user = get_current_user(
        request
    )

    return upload_logo(
        user,
        business_id,
        image,
    )


@router.delete(
    "/{business_id}/logo",
    auth=JWTAuth(),
)
def delete_business_logo(
    request,
    business_id: int,
):

    user = get_current_user(
        request
    )

    return delete_logo(
        user,
        business_id,
    )