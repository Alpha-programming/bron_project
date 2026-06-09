from ninja import Router

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

from core.utils.auth import (
    get_current_user
)

router = Router(tags=["Products"])


@router.post(
    "/create",
    response=ProductOutSchema
)
def create_product_view(
        request,
        data: ProductCreateSchema
):

    user = get_current_user(request)

    return create_product(
        user,
        data
    )


@router.get(
    "/",
    response=list[ProductListSchema]
)
def product_list(request):

    return get_products()


@router.get(
    "/{product_id}",
    response=ProductOutSchema
)
def product_detail(
        request,
        product_id: int
):

    return get_product(
        product_id
    )


@router.get(
    "/business/{business_id}",
    response=list[ProductListSchema]
)
def business_products(
        request,
        business_id: int
):

    return get_business_products(
        business_id
    )


@router.put(
    "/{product_id}",
    response=ProductOutSchema
)
def update_product_view(
        request,
        product_id: int,
        data: ProductUpdateSchema
):

    user = get_current_user(request)

    product = get_product(
        product_id
    )

    return update_product(
        user,
        product,
        data
    )


@router.delete(
    "/{product_id}"
)
def delete_product_view(
        request,
        product_id: int
):

    user = get_current_user(request)

    product = get_product(
        product_id
    )

    return delete_product(
        user,
        product
    )