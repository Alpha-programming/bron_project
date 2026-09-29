from ninja import Router, File
from ninja.files import UploadedFile
from core.security import JWTAuth
from core.models import User, Product
from core.schemas.common import ErrorSchema
from core.schemas.product import (
    ProductCreateSchema,
    ProductUpdateSchema,
    ProductOutSchema,
    ProductListSchema,
)
from core.services.product import (
    create_product,
    get_products,
    get_product,
    get_business_products,
    update_product,
    delete_product,
    upload_product_image,
    delete_product_image,
)
from typing import List

router = Router(tags=["Products"])


@router.post(
    "/create",
    auth=JWTAuth(),
    response={200: ProductOutSchema, 400: ErrorSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Create a product",
)
def create_product_view(request, data: ProductCreateSchema):
    """
    Adds a product to a business. JSON body; `description` is optional and
    is stored as an empty string when omitted or null. The photo is uploaded
    separately via POST /api/products/{product_id}/image.

    Auth: JWT, only the business owner.

    Errors: 400 - body is not JSON (e.g. multipart/form-data);
    401 - missing or invalid token; 403 - not the business owner;
    404 - business not found; 422 - missing or invalid fields.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_product(user, data)


@router.get("/", response=list[ProductListSchema])
def product_list(request):
    return get_products()


# --- FIXED: MOVED UP ABOVE THE DYNAMIC ID PARAMETER ---
@router.get("/search", response=List[ProductOutSchema])
def search_products(request, q: str):
    """
    Find warehouse retail inventory matches.
    """
    return Product.objects.filter(name__icontains=q)


@router.get("/business/{business_id}", response=list[ProductListSchema])
def business_products(request, business_id: int):
    return get_business_products(business_id)


@router.post(
    "/{product_id}/image",
    auth=JWTAuth(),
    response={200: ProductOutSchema, 400: ErrorSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Upload or replace the product photo",
)
def upload_image(
    request,
    product_id: int,
    image: UploadedFile = File(..., description="JPEG, PNG or WEBP, up to 5 MB"),
):
    """
    Uploads the product photo as multipart/form-data (file field `image`).
    An existing photo is replaced and its old file is deleted.

    Auth: JWT, only the owner of the product's business.

    Allowed types: JPEG, PNG, WEBP. Max size: 5 MB. The file content is
    checked, not only its Content-Type, and the stored file gets the
    extension of the real format (.jpg, .png or .webp).

    Returns the product with `image` as an absolute URL.

    Errors: 400 - wrong file type, not a real image or file larger than 5 MB;
    401 - missing or invalid token; 403 - not the business owner;
    404 - product not found.
    """
    return upload_product_image(request.auth, get_product(product_id), image)


@router.delete(
    "/{product_id}/image",
    auth=JWTAuth(),
    response={200: ProductOutSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Delete the product photo",
)
def remove_image(request, product_id: int):
    """
    Removes the product photo and deletes its file from storage.
    Safe to call when the product has no photo.

    Auth: JWT, only the owner of the product's business.

    Returns the product with `image: null`.

    Errors: 401 - missing or invalid token; 403 - not the business owner;
    404 - product not found.
    """
    return delete_product_image(request.auth, get_product(product_id))


@router.get("/{product_id}", response=ProductOutSchema)
def product_detail(request, product_id: int):
    return get_product(product_id)


@router.put(
    "/{product_id}",
    auth=JWTAuth(),
    response={200: ProductOutSchema, 400: ErrorSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Update a product",
)
def update_product_view(request, product_id: int, data: ProductUpdateSchema):
    """
    Partial update with a JSON body: only the sent fields change.
    `description: null` clears the description (stored as ""); null for
    `name`, `price` or `is_active` is rejected. The photo is changed via
    POST /api/products/{product_id}/image.

    Auth: JWT, only the owner of the product's business.

    Errors: 400 - body is not JSON (e.g. multipart/form-data) or a null
    `name`/`price`/`is_active`; 401 - missing or invalid token;
    403 - not the business owner; 404 - product not found;
    422 - invalid field values.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    product = get_product(product_id)
    return update_product(user, product, data)


@router.delete("/{product_id}", auth=JWTAuth(), summary="Delete a product")
def delete_product_view(request, product_id: int):
    """
    Deletes the product together with its photo file.

    Auth: JWT, only the owner of the product's business.

    Errors: 401 - missing or invalid token; 403 - not the business owner;
    404 - product not found.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    product = get_product(product_id)
    return delete_product(user, product)
