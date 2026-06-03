from ninja.errors import HttpError


def update_profile(user, data):

    if data.email is not None:
        user.email = data.email

    if data.phone is not None:
        user.phone = data.phone

    if data.language is not None:
        user.language = data.language

    if data.telegram_id is not None:
        user.telegram_id = data.telegram_id

    user.save()

    return user