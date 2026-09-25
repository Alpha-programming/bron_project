from typing import List

from ninja import Router

from core.schemas.category import CategoryOutSchema
from core.services.category import (
    get_active_categories,
    get_category_by_slug,
)

router = Router(tags=["Categories"])


@router.get("/", response=List[CategoryOutSchema])
def category_list(request):
    """
    Active categories with the number of approved businesses in each.
    Categories are managed in the admin panel.
    """
    return get_active_categories()


@router.get("/{slug}", response=CategoryOutSchema)
def category_detail(request, slug: str):
    return get_category_by_slug(slug)
