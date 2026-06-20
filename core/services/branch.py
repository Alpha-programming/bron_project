from ninja.errors import HttpError
from core.models import Branch, Business

def create_branch(user, data):
    try:
        business = Business.objects.get(id=data.business_id)
    except Business.DoesNotExist:
        raise HttpError(404, "Business not found")

    if business.owner != user:
        raise HttpError(403, "Permission denied")

    return Branch.objects.create(
        business=business,
        name=data.name,
        address=data.address,
        phone=data.phone,
        latitude=data.latitude,
        longitude=data.longitude,
    )

def get_branches():
    return Branch.objects.select_related("business").all()

def get_branch(branch_id):
    try:
        return Branch.objects.select_related("business").get(id=branch_id)
    except Branch.DoesNotExist:
        raise HttpError(404, "Branch not found")

def get_business_branches(business_id):
    return Branch.objects.filter(business_id=business_id)

def update_branch(user, branch, data):
    if branch.business.owner != user:
        raise HttpError(403, "Permission denied")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)

    branch.save()
    return branch

def delete_branch(user, branch):
    if branch.business.owner != user:
        raise HttpError(403, "Permission denied")

    branch.delete()
    return {"message": "Branch deleted successfully"}