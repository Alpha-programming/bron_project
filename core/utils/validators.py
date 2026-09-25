from ninja.errors import HttpError

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_MB = 5


def validate_image(file, max_mb: int = MAX_IMAGE_MB):
    """
    Rejects uploads that are not jpeg/png/webp or exceed max_mb megabytes.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HttpError(
            400,
            "Only JPEG, PNG or WEBP images are allowed"
        )

    if file.size > max_mb * 1024 * 1024:
        raise HttpError(
            400,
            f"Image must be smaller than {max_mb} MB"
        )
