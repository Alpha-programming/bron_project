from typing import List
from ninja import Router
from core.security import JWTAuth
from core.models import Favorite
from core.schemas.engagement import FavoriteOutSchema, FavoriteCreateSchema
from core.services.engagement import toggle_business_bookmark, remove_business_bookmark

router = Router(tags=["Favorites & Bookmarks"])

@router.post("/", auth=JWTAuth(), response=FavoriteOutSchema)
def save_favorite_business(request, payload: FavoriteCreateSchema):
    """
    Pins a selected commercial business hub into the consumer account tracking bookmarks index.
    """
    return toggle_business_bookmark(request.auth, payload)


@router.get("/", auth=JWTAuth(), response=List[FavoriteOutSchema])
def get_my_favorites(request):
    """
    Returns all bookmarked profiles grouped by the active authenticated consumer identity.
    """
    return Favorite.objects.filter(user=request.auth).select_related("business")


@router.delete("/{id}", auth=JWTAuth())
def drop_favorite_business(request, id: int):
    """
    Disables a customer bookmark collection reference record by identifier.
    """
    return remove_business_bookmark(request.auth, id)