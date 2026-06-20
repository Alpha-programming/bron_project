from ninja.errors import HttpError
from core.models import Service, Business

def create_service(user, data):
    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found")

    if business.owner != user:
        raise HttpError(403, "Permission denied")

    return Service.objects.create(
        business=business,
        title=data.title,
        description=data.description,
        category=data.category,
        duration=data.duration,
        price=data.price,
    )

def get_services():
    return Service.objects.filter(is_active=True).select_related("business")

def get_service(service_id: int):
    try:
        return Service.objects.select_related("business", "business__owner").get(id=service_id)
    except Service.DoesNotExist:
        raise HttpError(404, "Service not found")

def get_business_services(business_id: int):
    return Service.objects.filter(business_id=business_id, is_active=True)

def update_service(user, service, data):
    if service.business.owner != user:
        raise HttpError(403, "Permission denied")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)

    service.save()
    return service

def delete_service(user, service):
    if service.business.owner != user:
        raise HttpError(403, "Permission denied")

    service.delete()
    return {"message": "Service deleted successfully"}