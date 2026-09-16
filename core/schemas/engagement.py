from ninja import Schema
from typing import Optional
from datetime import datetime

# --- REVIEW SCHEMAS ---

class ReviewCreateSchema(Schema):
    business_id: int
    booking_id: Optional[int] = None
    rating: int
    comment: Optional[str] = None


class CustomerReviewCreateSchema(Schema):
    booking_id: int
    rating: int
    comment: Optional[str] = None


class ReviewUpdateSchema(Schema):
    rating: Optional[int] = None
    comment: Optional[str] = None


class ReviewOutSchema(Schema):
    id: int
    user_id: int
    user_username: str

    business_id: Optional[int] = None
    customer_id: Optional[int] = None
    booking_id: Optional[int] = None

    review_type: str

    rating: int
    comment: Optional[str] = None
    created_at: datetime

    @staticmethod
    def resolve_user_username(obj):
        return obj.user.username


class CustomerRatingSchema(Schema):
    user_id: int
    username: str
    rating: float
    reviews_count: int

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

