def working_day_bounds(day, open_time, close_time):
    """
    Opening/closing datetimes for a working day. A closing time at or before
    the opening time (e.g. 06:00-00:00) means "until the end of the day";
    slots are capped at 23:59 so they never cross midnight.
    """
    from datetime import datetime, time

    opening = datetime.combine(day, open_time)
    closing = datetime.combine(day, close_time)
    if closing <= opening:
        closing = datetime.combine(day, time(23, 59))
    return opening, closing


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
