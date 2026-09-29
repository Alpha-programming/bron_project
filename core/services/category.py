from django.db.models import Count, Q
from ninja.errors import HttpError

from core.models import Category


def _with_business_count():
    # Explicit ORDER BY: with the Count's GROUP BY Django drops Meta.ordering,
    # so PostgreSQL returned rows in any order and "Other" was not last
    return Category.objects.annotate(
        business_count=Count(
            "businesses",
            filter=Q(businesses__is_active=True),
        )
    ).order_by("order", "name")


def get_active_categories():
    return _with_business_count().filter(is_active=True)


def get_category_by_slug(slug: str):
    try:
        return _with_business_count().get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        raise HttpError(404, "Category not found")


def get_category_by_id(category_id: int):
    try:
        return Category.objects.get(id=category_id, is_active=True)
    except Category.DoesNotExist:
        raise HttpError(404, "Category not found")
