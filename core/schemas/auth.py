from typing import Optional

from ninja import Schema

class RegisterSchema(Schema):
    username: str
    email: str
    phone: str
    password: str

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
    email: str
    phone: str
    # Fixed: Fallback to a default string if field is missing or empty
    role: str = "client"

class MessageSchema(Schema):
    detail: str