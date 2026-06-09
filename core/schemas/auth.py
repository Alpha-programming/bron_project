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


class UserOutSchema(Schema):

    id: int
    username: str
    email: str
    phone: str
    role: str

class MessageSchema(Schema):
    detail: str