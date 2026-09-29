from ninja import Schema


class ErrorSchema(Schema):
    """Body of every HttpError response: {"detail": "..."}."""

    detail: str
