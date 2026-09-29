from ninja import Router, File, Form
from ninja.files import UploadedFile

from core.security import JWTAuth

from core.schemas.business_gallery import (
    BusinessGalleryOutSchema,
    BusinessGalleryDeleteSchema,
)
from core.schemas.common import ErrorSchema

from core.services.business_gallery import (
    MAX_SORT_ORDER,
    upload_business_image,
    get_business_gallery,
    get_gallery_image,
    update_business_image,
    delete_business_image,
)

from core.utils.auth import (
    get_current_user,
)
from core.utils.validators import MAX_IMAGE_MB

router = Router(tags=["Business Gallery"])

IMAGE_RULES = f"JPEG, PNG or WEBP, up to {MAX_IMAGE_MB} MB"

SORT_ORDER_RULES = "Display position: lower comes first, ties go by id"

@router.post(
    "/upload/{business_id}",
    auth=JWTAuth(),
    response={
        200: BusinessGalleryOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    summary="Upload a gallery image",
)
def upload_image(
    request,
    business_id: int,
    image: UploadedFile = File(..., description=IMAGE_RULES),
):
    """
    Adds one picture to the business gallery. JWT auth, business owner only.

    - multipart/form-data with the file field `image`: JPEG, PNG or WEBP, max 5 MB.
      The file content is checked, not only its Content-Type; the stored file
      gets the extension of the real format (.jpg, .png or .webp).
    - At most 20 images per business.
    - The picture is appended to the end: its `sort_order` is the current
      maximum + 1 (0 for the first image), capped at 2147483647.

    Errors: 400 wrong file type or not a real image, file too large or gallery full;
    401 missing or invalid token; 403 not the owner; 404 business not found.
    """

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
    summary="List gallery images of a business",
)
def gallery_list(
    request,
    business_id: int,
):
    """
    Public. Images ordered by `sort_order`, then by `id`.
    An unknown business gives an empty list.
    """

    return get_business_gallery(
        business_id
    )


@router.put(
    "/{image_id}",
    auth=JWTAuth(),
    response={
        200: BusinessGalleryOutSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    summary="Replace a gallery image or change its position",
)
def update_image(
    request,
    image_id: int,
    image: UploadedFile = File(None, description=f"New picture: {IMAGE_RULES}"),
    sort_order: int = Form(None, ge=0, le=MAX_SORT_ORDER, description=SORT_ORDER_RULES),
):
    """
    Updates one gallery image. JWT auth, business owner only.

    multipart/form-data, at least one field is required:
    - `image`: new picture that replaces the current file (the old file is
      deleted from storage). JPEG, PNG or WEBP, max 5 MB; the content is
      checked and the stored file gets the extension of the real format.
    - `sort_order`: integer from 0 to 2147483647, display position; lower
      comes first, ties go by id. Other images are not renumbered.

    Errors: 400 neither field sent, wrong file type, not a real image or file too large;
    401 missing or invalid token; 403 not the owner; 404 image not found;
    422 sort_order is not an integer in range.
    """

    user = get_current_user(
        request
    )

    gallery_image = get_gallery_image(
        image_id
    )

    return update_business_image(
        user,
        gallery_image,
        image=image,
        sort_order=sort_order,
    )


@router.delete(
    "/{image_id}",
    auth=JWTAuth(),
    response={
        200: BusinessGalleryDeleteSchema,
        401: ErrorSchema,
        403: ErrorSchema,
        404: ErrorSchema,
    },
    summary="Delete a gallery image",
)
def delete_image(
    request,
    image_id: int,
):
    """
    Deletes the image and its file. JWT auth, business owner only.
    The remaining images keep their `sort_order`.

    Errors: 401 missing or invalid token; 403 not the owner;
    404 image not found.
    """

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
