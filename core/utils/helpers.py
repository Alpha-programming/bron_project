def absolute_media_url(request, filefield):
    """
    Builds an absolute URL for an ImageField/FileField, or None when empty.
    """
    if not filefield:
        return None

    return request.build_absolute_uri(filefield.url)
