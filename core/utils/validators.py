import os

from ninja.errors import HttpError
from PIL import Image

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",  # non-standard alias some clients send for JPEG
    "image/png",
    "image/webp",
}

# Pillow format name -> extension the stored file gets
IMAGE_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

MAX_IMAGE_MB = 5

WRONG_TYPE_MESSAGE = "Only JPEG, PNG or WEBP images are allowed"


def validate_image(file, max_mb: int = MAX_IMAGE_MB):
    """
    Rejects uploads that are not jpeg/png/webp or exceed max_mb megabytes.

    The declared Content-Type is client-controlled, so the bytes are also
    decoded with Pillow, and file.name gets the extension of the detected
    format: HTML or SVG sent as image/png must never land in /media as .html.
    """
    if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
        raise HttpError(400, WRONG_TYPE_MESSAGE)

    if file.size > max_mb * 1024 * 1024:
        raise HttpError(
            400,
            f"Image must be smaller than {max_mb} MB"
        )

    try:
        file.seek(0)
        # formats= keeps Pillow from even trying other decoders
        with Image.open(file, formats=list(IMAGE_EXTENSIONS)) as image:
            image_format = image.format
            image.verify()
    except Exception:
        # Not an image, truncated/corrupt data or another format
        raise HttpError(400, WRONG_TYPE_MESSAGE)
    finally:
        # The file is saved from the start later on
        file.seek(0)

    base = os.path.splitext(file.name or "")[0] or "image"
    file.name = base + IMAGE_EXTENSIONS[image_format]
