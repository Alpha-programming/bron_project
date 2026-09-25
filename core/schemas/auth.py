from typing import Optional

from ninja import Schema

from core.utils.helpers import absolute_media_url

class RegisterSchema(Schema):
    username: str
    email: str
    phone: str
    password: str
    first_name: str = ""
    last_name: str = ""

class LoginSchema(Schema):
    username: str
    password: str

class LoginResponseSchema(Schema):
    access_token: str
    user_id: int
    username: str
    tg_token: Optional[str] = None

class UserOutSchema(Schema):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    phone: str
    avatar: Optional[str] = None
    role: str = "customer"

    @staticmethod
    def resolve_avatar(obj, context):
        return absolute_media_url(context["request"], obj.avatar)

class MessageSchema(Schema):
    detail: str