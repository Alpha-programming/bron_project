from ninja.errors import HttpError
from core.models import Product, Business
from core.utils.validators import validate_image

def create_product(user, data):
    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found")

    if business.owner != user:
        raise HttpError(403, "Permission denied")

    return Product.objects.create(
        business=business,
        name=data.name,
        # The column is NOT NULL; a missing description is stored as ""
        description=data.description or "",
        price=data.price,
    )

def get_products():
    return Product.objects.filter(is_active=True)

def get_product(product_id):
    try:
        return Product.objects.select_related("business").get(id=product_id)
    except Product.DoesNotExist:
        raise HttpError(404, "Product not found")

def get_business_products(business_id):
    return Product.objects.filter(business_id=business_id, is_active=True)

def update_product(user, product, data):
    if product.business.owner != user:
        raise HttpError(403, "Permission denied")

    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            # All product columns are NOT NULL: null clears the description,
            # for the other fields it is a client error rather than a 500
            if field != "description":
                raise HttpError(400, f"{field} cannot be null")
            value = ""
        setattr(product, field, value)

    product.save()
    return product

def upload_product_image(user, product, image):
    if product.business.owner != user:
        raise HttpError(403, "Permission denied")

    validate_image(image)

    old_name = product.image.name if product.image else None

    product.image = image
    product.save(update_fields=["image"])

    # Drop the old file only once the new one is stored, so a failed save
    # never leaves the product pointing at a missing file
    if old_name:
        product.image.storage.delete(old_name)

    return product

def delete_product_image(user, product):
    if product.business.owner != user:
        raise HttpError(403, "Permission denied")

    if product.image:
        product.image.delete(save=False)

    product.image = None
    product.save(update_fields=["image"])
    return product

def delete_product(user, product):
    if product.business.owner != user:
        raise HttpError(403, "Permission denied")

    image = product.image
    product.delete()

    # Deleting the row does not touch storage, remove the photo explicitly
    if image:
        image.delete(save=False)

    return {"message": "Product deleted"}
