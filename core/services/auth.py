from ninja.errors import HttpError

from django.contrib.auth import authenticate

from core.models import User
from core.utils.jwt import create_access_token


def register_user(data):

    if User.objects.filter(
        username=data.username
    ).exists():

        raise HttpError(
            400,
            "Username already exists"
        )

    if User.objects.filter(
        email=data.email
    ).exists():

        raise HttpError(
            400,
            "Email already exists"
        )

    user = User.objects.create_user(
        username=data.username,
        email=data.email,
        phone=data.phone,
        password=data.password,
    )

    return user


def login_user(data):

    user = authenticate(
        username=data.username,
        password=data.password,
    )

    if not user:

        raise HttpError(
            401,
            "Invalid username or password"
        )

    token = create_access_token(user)

    return {
        "access_token": token,
        "user_id": user.id,
        "username": user.username,
    }