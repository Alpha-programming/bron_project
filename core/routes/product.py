from ninja import Router
from core.security import JWTAuth
from core.models import User, Product
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
)
from typing import List

router = Router(tags=["Products"])


@router.post("/create", auth=JWTAuth(), response=ProductOutSchema)
def create_product_view(request, data: ProductCreateSchema):
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


@router.get("/{product_id}", response=ProductOutSchema)
def product_detail(request, product_id: int):
    return get_product(product_id)


@router.put("/{product_id}", auth=JWTAuth(), response=ProductOutSchema)
def update_product_view(request, product_id: int, data: ProductUpdateSchema):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    product = get_product(product_id)
    return update_product(user, product, data)


@router.delete("/{product_id}", auth=JWTAuth())
def delete_product_view(request, product_id: int):
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    product = get_product(product_id)
    return delete_product(user, product)