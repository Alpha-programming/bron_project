from ninja.errors import HttpError

from core.models import (
    Product,
    Business,
)


def create_product(user, data):

    try:

        business = Business.objects.get(
            id=data.business_id
        )

    except Business.DoesNotExist:

        raise HttpError(
            404,
            "Business not found"
        )

    if business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    return Product.objects.create(
        business=business,
        name=data.name,
        description=data.description,
        price=data.price,
    )


def get_products():

    return Product.objects.filter(
        is_active=True
    )


def get_product(product_id):

    try:

        return Product.objects.get(
            id=product_id
        )

    except Product.DoesNotExist:

        raise HttpError(
            404,
            "Product not found"
        )


def get_business_products(business_id):

    return Product.objects.filter(
        business_id=business_id,
        is_active=True
    )


def update_product(
        user,
        product,
        data
):

    if product.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    for field, value in data.model_dump(
        exclude_unset=True
    ).items():

        setattr(
            product,
            field,
            value
        )

    product.save()

    return product


def delete_product(
        user,
        product
):

    if product.business.owner != user:

        raise HttpError(
            403,
            "Permission denied"
        )

    product.delete()

    return {
        "message": "Product deleted"
    }