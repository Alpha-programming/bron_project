# Aliased so the `date` query parameter below can keep its public name
from datetime import date as date_type

from ninja import Router, File, Query
from ninja.files import UploadedFile
from core.security import JWTAuth
from core.models import User, Service
from core.schemas.common import ErrorSchema
from core.schemas.service import (
    ServiceCreateSchema,
    ServiceUpdateSchema,
    ServiceOutSchema,
    ServiceListSchema,
    ServiceAvailabilityOutSchema,
    ServiceAvailableDateSchema,
    SLOT_STAFF_DESCRIPTION,
)
from core.services.service import (
    create_service,
    get_services,
    get_service,
    get_business_services,
    update_service,
    delete_service,
    get_distinct_service_categories,
    upload_service_image,
    delete_service_image,
    get_service_availability,
    get_service_available_dates,
    MAX_AVAILABILITY_DAYS,
)
from typing import List, Optional

router = Router(tags=["Services"])


@router.post(
    "/create",
    auth=JWTAuth(),
    response={200: ServiceOutSchema, 400: ErrorSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Create a service",
)
def create_service_view(request, payload: ServiceCreateSchema):
    """
    Creates a service in one of the current user's businesses.

    Auth: JWT (Bearer token); only the owner of `business_id` may add services.

    `availability` (optional) is the service's own schedule:
    `[{"date": "YYYY-MM-DD", "times": ["HH:MM", ...]}]`. Each time starts a slot of
    `duration` minutes. Omit it or send `[]` to make the service bookable within the
    business working hours. With a schedule the service can be booked only at the
    listed dates and times (working hours are ignored); a date with empty `times`
    is a day off. The stored schedule is returned sorted, with duplicate times removed.

    Errors: 400 - a scheduled slot would end after 23:59 (time + duration);
    401 - missing or invalid token; 403 - the business belongs to another user;
    404 - business not found; 422 - malformed body, e.g. a date not in YYYY-MM-DD,
    a time not in HH:MM or the same date listed twice.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_service(user, payload)


@router.get("/", response=list[ServiceListSchema], summary="List active services")
def service_list(request):
    """
    All active services. Auth: none (public).
    `availability` is the service's own schedule, `[]` when it follows the
    business working hours.
    """
    return get_services()


@router.get("/categories", response=List[str], summary="List service categories")
def service_categories_view(request):
    """
    Fetches a unique list of all service categories to build filtering menus.
    """
    return get_distinct_service_categories()


# --- FIXED: MOVED ABOVE THE DYNAMIC ID PATHS & FILTER CHANGED TO TITLE ---
@router.get("/search", response=List[ServiceOutSchema], summary="Search services by title")
def search_services(request, q: str):
    """
    Services whose title contains `q` (case-insensitive). Auth: none (public).
    """
    return Service.objects.filter(title__icontains=q)


@router.get(
    "/business/{business_id}",
    response=list[ServiceListSchema],
    summary="List active services of a business",
)
def business_services(request, business_id: int):
    """
    Active services of one business. Auth: none (public).
    `availability` is the service's own schedule, `[]` when it follows the
    business working hours.
    """
    return get_business_services(business_id)


@router.get(
    "/{service_id}/availability",
    response={200: ServiceAvailabilityOutSchema, 404: ErrorSchema},
    summary="Free time slots of a service on a date",
)
def service_availability(
    request,
    service_id: int,
    date: date_type = Query(..., description="Day to check, YYYY-MM-DD"),
    staff_id: Optional[int] = Query(None, description=SLOT_STAFF_DESCRIPTION),
):
    """
    Time slots for one day with the number of free places in each.
    Auth: none (public).

    Where the slots come from:
    - service with its own schedule (`availability` not empty): exactly the start
      times listed for this date, each ending at start + `duration`; working hours
      are ignored, so times outside them and days without working hours are offered.
      A date that is not listed, or is listed with empty `times`, has no slots.
    - service without a schedule: consecutive slots of `duration` minutes inside
      the business working hours of that weekday.

    In both cases blocked dates have no slots, past dates and slots that already
    started today are not listed, and `available_spots` is `capacity` minus the
    guests of all pending/confirmed bookings of the service overlapping the slot,
    whichever staff member they are with.

    With `staff_id`, slots that overlap a pending/confirmed booking of that staff
    member in any service are also returned with `is_available: false` and
    `available_spots: 0`, matching the check of `POST /api/bookings/create`.

    Errors: 404 - service not found, or `staff_id` is not staff of this business;
    422 - `date` missing or not YYYY-MM-DD.
    """
    return get_service_availability(get_service(service_id), date, staff_id)


@router.get(
    "/{service_id}/available-dates",
    response={200: List[ServiceAvailableDateSchema], 400: ErrorSchema, 404: ErrorSchema},
    summary="Dates with free slots for a service",
)
def service_available_dates(
    request,
    service_id: int,
    days: int = Query(
        14, description=f"How many days to look ahead, today included (1-{MAX_AVAILABILITY_DAYS})"
    ),
    staff_id: Optional[int] = Query(None, description=SLOT_STAFF_DESCRIPTION),
):
    """
    Dates from today up to `days` ahead that have at least one free slot,
    with the number of such slots. Auth: none (public).

    Uses the same slot rules as `GET /api/services/{service_id}/availability`:
    a service with its own schedule is offered only on its listed dates and
    times (working hours ignored); otherwise the business working hours apply.
    Blocked dates, days off and fully booked dates are left out; with
    `staff_id`, so are dates on which that staff member is busy in every slot.

    Errors: 400 - `days` out of range; 404 - service not found, or `staff_id`
    is not staff of this business.
    """
    return get_service_available_dates(get_service(service_id), days, staff_id)


@router.post(
    "/{service_id}/image",
    auth=JWTAuth(),
    response={200: ServiceOutSchema, 400: ErrorSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Upload or replace the service image",
)
def upload_image(
    request,
    service_id: int,
    image: UploadedFile = File(..., description="JPEG, PNG or WEBP, up to 5 MB"),
):
    """
    Sets the service image (multipart/form-data, field `image`); the previous
    file is deleted. Auth: JWT (Bearer token); business owner only.
    The file content is checked, not only its Content-Type, and the stored
    file gets the extension of the real format (.jpg, .png or .webp).

    Errors: 400 - not a real JPEG/PNG/WEBP image or larger than 5 MB; 401 - missing or
    invalid token; 403 - not the business owner; 404 - service not found.
    """
    return upload_service_image(request.auth, get_service(service_id), image)


@router.delete(
    "/{service_id}/image",
    auth=JWTAuth(),
    response={200: ServiceOutSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Remove the service image",
)
def remove_image(request, service_id: int):
    """
    Deletes the service image; `image` becomes null.
    Auth: JWT (Bearer token); business owner only.

    Errors: 401 - missing or invalid token; 403 - not the business owner;
    404 - service not found.
    """
    return delete_service_image(request.auth, get_service(service_id))


@router.get(
    "/{service_id}",
    response={200: ServiceOutSchema, 404: ErrorSchema},
    summary="Get a service",
)
def service_detail(request, service_id: int):
    """
    One service with its own schedule in `availability` (`[]` when it follows
    the business working hours). Auth: none (public).

    Errors: 404 - service not found.
    """
    return get_service(service_id)


@router.put(
    "/{service_id}",
    auth=JWTAuth(),
    response={200: ServiceOutSchema, 400: ErrorSchema, 401: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    summary="Update a service",
)
def update_service_view(request, service_id: int, payload: ServiceUpdateSchema):
    """
    Partial update: only the fields sent are changed.
    Auth: JWT (Bearer token); only the business owner may edit the service.

    `availability`: omit it to keep the current schedule; a list replaces the
    whole schedule (`[{"date": "YYYY-MM-DD", "times": ["HH:MM", ...]}]`);
    `null` or `[]` removes it, so the service follows the business working
    hours again. Existing bookings are not changed.

    Errors: 400 - a scheduled slot would end after 23:59, also when only
    `duration` is changed and the stored schedule no longer fits;
    401 - missing or invalid token; 403 - not the business owner;
    404 - service not found; 422 - malformed body (bad date/time format,
    duplicate date).
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    service = get_service(service_id)
    return update_service(user, service, payload)


@router.delete("/{service_id}", auth=JWTAuth(), summary="Delete a service")
def delete_service_view(request, service_id: int):
    """
    Deletes the service. Auth: JWT (Bearer token); business owner only.

    Errors: 401 - missing or invalid token; 403 - not the business owner;
    404 - service not found.
    """
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    service = get_service(service_id)
    return delete_service(user, service)