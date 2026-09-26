from datetime import timedelta

from django.utils import timezone
from ninja.errors import HttpError

from core.models import BusinessApplication

# The form is public, so cap how many applications one IP can send
RATE_LIMIT = 10
RATE_LIMIT_WINDOW = timedelta(hours=1)


def create_business_application(data, user, ip):

    if ip:
        since = timezone.now() - RATE_LIMIT_WINDOW

        recent = BusinessApplication.objects.filter(
            ip=ip,
            created_at__gte=since,
        ).count()

        if recent >= RATE_LIMIT:
            raise HttpError(
                429,
                "Too many applications, please try again later"
            )

    return BusinessApplication.objects.create(
        user=user,
        ip=ip,
        **data.model_dump()
    )
