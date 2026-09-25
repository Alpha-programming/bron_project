def get_client_ip(request):
    """
    Real client address behind nginx (first X-Forwarded-For entry), else REMOTE_ADDR.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def absolute_media_url(request, filefield):
    """
    Builds an absolute URL for an ImageField/FileField, or None when empty.
    """
    if not filefield:
        return None

    return request.build_absolute_uri(filefield.url)
