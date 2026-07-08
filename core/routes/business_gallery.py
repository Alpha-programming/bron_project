from ninja import Router, File
from ninja.files import UploadedFile

from core.security import JWTAuth

from core.schemas.business_gallery import (
    BusinessGalleryOutSchema,
)

from core.services.business_gallery import (
    upload_business_image,
    get_business_gallery,
    get_gallery_image,
    delete_business_image,
)

from core.utils.auth import (
    get_current_user,
)

router = Router(tags=["Business Gallery"])


@router.post(
    "/upload/{business_id}",
    auth=JWTAuth(),
    response=BusinessGalleryOutSchema,
)
def upload_image(
    request,
    business_id: int,
    image: UploadedFile = File(...),
):

    user = get_current_user(
        request
    )

    return upload_business_image(
        user,
        business_id,
        image,
    )


@router.get(
    "/business/{business_id}",
    response=list[BusinessGalleryOutSchema],
)
def gallery_list(
    request,
    business_id: int,
):

    return get_business_gallery(
        business_id
    )


@router.delete(
    "/{image_id}",
    auth=JWTAuth(),
)
def delete_image(
    request,
    image_id: int,
):

    user = get_current_user(
        request
    )

    image = get_gallery_image(
        image_id
    )

    return delete_business_image(
        user,
        image,
    )