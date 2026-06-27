from ninja import Schema
from typing import Optional
from datetime import datetime

# --- REVIEW SCHEMAS ---
class ReviewCreateSchema(Schema):
    business_id: int
    rating: int  # e.g., 1 to 5
    comment: Optional[str] = None

class ReviewUpdateSchema(Schema):
    rating: Optional[int] = None
    comment: Optional[str] = None

class ReviewOutSchema(Schema):
    id: int
    user_id: int
    user_username: str
    business_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    @staticmethod
    def resolve_user_username(obj):
        return obj.user.username

# --- FAVORITE SCHEMAS ---
class FavoriteCreateSchema(Schema):
    business_id: int

class FavoriteOutSchema(Schema):
    id: int
    user_id: int
    business_id: int
    business_name: str
    created_at: datetime

    @staticmethod
    def resolve_business_name(obj):
        return obj.business.name