import base64
import os
import requests
import sys
import uuid
from datetime import date, timedelta
from io import BytesIO


# ============================================================
# CONFIGURATION
# ============================================================

# LOCAL
BASE_URL = os.getenv("BRON_API_URL", "http://127.0.0.1:8001/api")

# PRODUCTION — use later:
# BASE_URL = "https://api.bronofficial.com/api"

TIMEOUT = 15
RUN_ID = uuid.uuid4().hex[:8]

# The report uses emoji; a redirected stdout on Windows defaults to a legacy
# code page that can't encode them
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# GLOBAL STATE
# ============================================================

CUSTOMER_TOKEN = None
OWNER_TOKEN = None

CUSTOMER_HEADERS = {}
OWNER_HEADERS = {}

CUSTOMER_ID = None
OWNER_ID = None

BUSINESS_ID = None
BRANCH_ID = None
SERVICE_ID = None
PRODUCT_ID = None
STAFF_ID = None

BOOKING_ID = None
BOOKING_DATE = date.today() + timedelta(days=7)
BUSINESS_ACTIVE = False

# Second service of the business with its own schedule (availability)
SCHEDULED_SERVICE_ID = None

# Objects of another business (owned by the customer), used to check that
# foreign ids are rejected
FOREIGN = {}

OTHER_CATEGORY_ID = None

WORKING_HOURS_ID = None
BLOCKED_DATE_ID = None
BLOCKED_DATE = date.today() + timedelta(days=30)

BUSINESS_REVIEW_ID = None
CUSTOMER_REVIEW_ID = None
FAVORITE_ID = None

PASSED = 0
FAILED = 0
SKIPPED = 0


# ============================================================
# HELPERS
# ============================================================

def print_section(title):
    print("\n")
    print("=" * 90)
    print(title)
    print("=" * 90)


def print_response_body(response):
    if response is None:
        return

    try:
        print("    Response:", response.json())
    except Exception:
        print("    Response:", response.text[:1500])


def request(
    method,
    endpoint,
    *,
    headers=None,
    json=None,
    params=None,
    files=None,
    data=None,
    expected=(200,),
    name=None,
):
    """
    Sends one counted request. `json` is the usual body; `files` (and
    optionally `data`) send multipart/form-data instead, e.g.
    files={"image": ("a.png", png_bytes, "image/png")}. A plain form field
    goes as files={"sort_order": (None, "3")} so the body stays multipart.
    """
    global PASSED, FAILED

    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
            files=files,
            data=data,
            timeout=TIMEOUT,
        )

    except requests.RequestException as exc:
        FAILED += 1

        print(
            f"❌ {method.upper():6} "
            f"{name or endpoint:<55} "
            f"CONNECTION ERROR"
        )

        print(f"    {exc}")
        return None

    success = response.status_code in expected

    if success:
        PASSED += 1
        symbol = "✅"
    else:
        FAILED += 1
        symbol = "❌"

    print(
        f"{symbol} {method.upper():6} "
        f"{name or endpoint:<55} "
        f"{response.status_code}"
    )

    if not success:
        print_response_body(response)

    return response


def skip_test(name, reason):
    global SKIPPED

    SKIPPED += 1

    print(
        f"⚠️ SKIP   {name:<55} "
        f"{reason}"
    )


def check(name, condition, details=None):
    """
    Counted assertion on response content: a wrong body is a failure just
    like a wrong status code.
    """
    global PASSED, FAILED

    if condition:
        PASSED += 1
        print(f"✅ {'CHECK':6} {name}")
    else:
        FAILED += 1
        print(f"❌ {'CHECK':6} {name}")
        if details is not None:
            print(f"    Got: {details}")

    return bool(condition)


def is_ok(response, status=200):
    return response is not None and response.status_code == status


def detail_of(response):
    body = get_json(response)
    return body.get("detail") if isinstance(body, dict) else None


def check_detail(name, response, expected_detail):
    """Checks the {"detail": ...} message of an error response."""
    if response is None:
        return False
    return check(name, detail_of(response) == expected_detail, detail_of(response))


def raw(method, endpoint, **kwargs):
    """Uncounted request for bulk setup/cleanup; None on connection error."""
    try:
        return requests.request(method, f"{BASE_URL}{endpoint}", timeout=TIMEOUT, **kwargs)
    except requests.RequestException:
        return None


# 1x1 PNG, used only when Pillow is not installed
FALLBACK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

IMAGE_TYPES = {
    "PNG": ("png", "image/png"),
    "JPEG": ("jpg", "image/jpeg"),
    "WEBP": ("webp", "image/webp"),
}


def make_image(color="red", fmt="PNG"):
    try:
        from PIL import Image
    except ImportError:
        return FALLBACK_PNG, "PNG"

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color).save(buffer, format=fmt)
    return buffer.getvalue(), fmt


def image_upload(color="red", fmt="PNG", field="image"):
    """files= payload with one small generated picture."""
    content, fmt = make_image(color, fmt)
    ext, mime = IMAGE_TYPES[fmt]
    label = "".join(ch for ch in str(color) if ch.isalnum())
    return {field: (f"bron_{RUN_ID}_{label}.{ext}", content, mime)}


def is_absolute_url(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def media_status(url):
    """Status code of GET on a media URL, None when it can't be fetched."""
    if not is_absolute_url(url):
        return None
    try:
        return requests.get(url, timeout=TIMEOUT).status_code
    except requests.RequestException:
        return None


def get_json(response):
    if response is None:
        return {}

    try:
        return response.json()
    except Exception:
        return {}


def get_id(response, *possible_keys):
    """
    Extract an ID from different API response styles.

    Supported examples:

        {"id": 10}

        {"business_id": 10}

        {"booking_id": 20}

        {
            "business": {
                "id": 10
            }
        }

        {
            "data": {
                "id": 10
            }
        }
    """

    data = get_json(response)

    if not isinstance(data, dict):
        return None

    # --------------------------------------------------------
    # STANDARD ID
    # --------------------------------------------------------

    if data.get("id") is not None:
        return data["id"]

    # --------------------------------------------------------
    # EXPLICIT KEYS
    # --------------------------------------------------------

    for key in possible_keys:
        if data.get(key) is not None:
            return data[key]

    # --------------------------------------------------------
    # COMMON BRON RESPONSE KEYS
    # --------------------------------------------------------

    common_keys = (
        "business_id",
        "branch_id",
        "service_id",
        "product_id",
        "staff_id",
        "booking_id",
        "working_hours_id",
        "blocked_date_id",
        "review_id",
        "favorite_id",
        "user_id",
    )

    for key in common_keys:
        if data.get(key) is not None:
            return data[key]

    # --------------------------------------------------------
    # WRAPPED OBJECTS
    # --------------------------------------------------------

    wrapper_keys = (
        "business",
        "branch",
        "service",
        "product",
        "staff",
        "booking",
        "working_hours",
        "blocked_date",
        "review",
        "favorite",
        "user",
        "data",
        "result",
    )

    for key in wrapper_keys:

        value = data.get(key)

        if isinstance(value, dict):

            if value.get("id") is not None:
                return value["id"]

            for id_key in common_keys:
                if value.get(id_key) is not None:
                    return value[id_key]

    return None


def run_django_locally(code):
    """
    Runs a snippet through manage.py shell. Works only against a local
    server, where this script and the API share the same database.
    """
    if "127.0.0.1" not in BASE_URL and "localhost" not in BASE_URL:
        return False

    manage = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manage.py")

    if not os.path.exists(manage):
        return False

    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            manage,
            "shell",
            "-c",
            code,
        ],
        capture_output=True,
    )

    return result.returncode == 0


# ============================================================
# STEP 0 — SERVER
# ============================================================

def test_server():
    print_section("STEP 0 — SERVER")

    response = request(
        "GET",
        "/",
        expected=(200,),
        name="/api/",
    )

    return (
        response is not None
        and response.status_code == 200
    )


# ============================================================
# STEP 1 — AUTHENTICATION
# ============================================================

def test_authentication():

    global CUSTOMER_TOKEN
    global OWNER_TOKEN

    global CUSTOMER_HEADERS
    global OWNER_HEADERS

    global CUSTOMER_ID
    global OWNER_ID

    print_section("STEP 1 — AUTHENTICATION")

    # --------------------------------------------------------
    # CUSTOMER REGISTER
    # --------------------------------------------------------

    customer_username = f"customer_{RUN_ID}"

    customer_payload = {
        "username": customer_username,
        "email": f"{customer_username}@bron.test",
        "password": "SecurePassword123!",
        "phone": f"+99890{RUN_ID[:7]}",
    }

    request(
        "POST",
        "/auth/register",
        json=customer_payload,
        expected=(200, 201),
        name="Register customer",
    )

    # --------------------------------------------------------
    # CUSTOMER LOGIN
    # --------------------------------------------------------

    response = request(
        "POST",
        "/auth/login",
        json={
            "username": customer_username,
            "password": "SecurePassword123!",
        },
        expected=(200,),
        name="Login customer",
    )

    data = get_json(response)

    CUSTOMER_TOKEN = data.get("access_token")

    if CUSTOMER_TOKEN:
        CUSTOMER_HEADERS = {
            "Authorization": f"Bearer {CUSTOMER_TOKEN}"
        }

    # --------------------------------------------------------
    # CUSTOMER ME
    # --------------------------------------------------------

    response = request(
        "GET",
        "/auth/me",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Customer /auth/me",
    )

    CUSTOMER_ID = get_id(response)

    # --------------------------------------------------------
    # OWNER REGISTER
    # --------------------------------------------------------

    owner_username = f"owner_{RUN_ID}"

    owner_payload = {
        "username": owner_username,
        "email": f"{owner_username}@bron.test",
        "password": "SecurePassword123!",
        "phone": f"+99891{RUN_ID[:7]}",
    }

    request(
        "POST",
        "/auth/register",
        json=owner_payload,
        expected=(200, 201),
        name="Register owner",
    )

    # --------------------------------------------------------
    # OWNER LOGIN
    # --------------------------------------------------------

    response = request(
        "POST",
        "/auth/login",
        json={
            "username": owner_username,
            "password": "SecurePassword123!",
        },
        expected=(200,),
        name="Login owner",
    )

    data = get_json(response)

    OWNER_TOKEN = data.get("access_token")

    if OWNER_TOKEN:
        OWNER_HEADERS = {
            "Authorization": f"Bearer {OWNER_TOKEN}"
        }

    # --------------------------------------------------------
    # OWNER ME
    # --------------------------------------------------------

    response = request(
        "GET",
        "/auth/me",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Owner /auth/me",
    )

    OWNER_ID = get_id(response)

    print()
    print("Customer ID:", CUSTOMER_ID)
    print("Owner ID:   ", OWNER_ID)

    return bool(
        CUSTOMER_TOKEN
        and OWNER_TOKEN
        and CUSTOMER_ID
        and OWNER_ID
    )


# ============================================================
# STEP 2 — USER PROFILE
# ============================================================

def test_user_profile():

    print_section("STEP 2 — USER PROFILE")

    response = request(
        "GET",
        "/users/profile",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Customer profile",
    )

    if response is not None and response.status_code == 200:

        data = get_json(response)

        print(
            "    Customer rating:",
            data.get("rating")
        )

        print(
            "    Customer reviews:",
            data.get("reviews_count")
        )

    request(
        "GET",
        "/users/profile",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Owner profile",
    )


# ============================================================
# STEP 2.1 — NOTIFICATION SETTINGS
# ============================================================

NOTIFICATION_DEFAULTS = {
    "push": True,
    "email": True,
    "bookingReminder": True,
    "promotions": False,
}


def test_notification_settings():

    print_section("STEP 2.1 — NOTIFICATION SETTINGS")

    response = request(
        "GET",
        "/users/profile/notifications",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Notification settings (defaults)",
    )

    if is_ok(response):
        check(
            "New account: push/email/bookingReminder on, promotions off",
            response.json() == NOTIFICATION_DEFAULTS,
            response.json(),
        )

    response = request(
        "PUT",
        "/users/profile/notifications",
        headers=CUSTOMER_HEADERS,
        json={"promotions": True},
        expected=(200,),
        name="Enable promotions only (partial PUT)",
    )

    if is_ok(response):
        check(
            "Partial PUT changes only promotions",
            response.json() == {**NOTIFICATION_DEFAULTS, "promotions": True},
            response.json(),
        )

    response = request(
        "PUT",
        "/users/profile/notifications",
        headers=CUSTOMER_HEADERS,
        json={"push": False, "email": None},
        expected=(200,),
        name="Disable push, email=null keeps value",
    )

    expected_settings = {
        "push": False,
        "email": True,
        "bookingReminder": True,
        "promotions": True,
    }

    if is_ok(response):
        check(
            "push off, null email kept, promotions still on",
            response.json() == expected_settings,
            response.json(),
        )

    response = request(
        "GET",
        "/users/profile/notifications",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Notification settings persisted",
    )

    if is_ok(response):
        check(
            "GET returns the saved settings",
            response.json() == expected_settings,
            response.json(),
        )

    response = request(
        "GET",
        "/users/profile/notifications",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Owner settings unaffected",
    )

    if is_ok(response):
        check(
            "Another user still has the defaults",
            response.json() == NOTIFICATION_DEFAULTS,
            response.json(),
        )

    request(
        "PUT",
        "/users/profile/notifications",
        headers=CUSTOMER_HEADERS,
        json={"push": "maybe"},
        expected=(422,),
        name="Non-boolean setting rejected",
    )

    request(
        "GET",
        "/users/profile/notifications",
        expected=(401,),
        name="Settings without token rejected",
    )

    request(
        "PUT",
        "/users/profile/notifications",
        json={"push": True},
        expected=(401,),
        name="Settings update without token rejected",
    )


# ============================================================
# STEP 2.2 — CATEGORIES
# ============================================================

def test_categories():

    global OTHER_CATEGORY_ID

    print_section("STEP 2.2 — CATEGORIES")

    response = request(
        "GET",
        "/categories/",
        expected=(200,),
        name="Category list",
    )

    if is_ok(response):
        categories = response.json()
        slugs = [c.get("slug") for c in categories]
        other = next((c for c in categories if c.get("slug") == "other"), None)

        check('Category "other" is listed', other is not None, slugs)

        if other is not None:
            OTHER_CATEGORY_ID = other.get("id")
            check('"other" is named "Other"', other.get("name") == "Other", other)
            if slugs[-1] != "other":
                print(f"    ⚠️  \"other\" is not the last category: {slugs}")

    request(
        "GET",
        "/categories/other",
        expected=(200,),
        name="Category detail: other",
    )


# ============================================================
# STEP 3 — BUSINESS
# ============================================================

def test_business():

    global BUSINESS_ID

    print_section("STEP 3 — BUSINESS")

    business_payload = {
        "name": f"BRON Test Business {RUN_ID}",
        "description": "Automated BRON integration testing business.",
        "category_id": 1,
        "address": "Tashkent",
        "phone": f"+99893{RUN_ID[:7]}",
        "email": f"business{RUN_ID}@example.com",
        "owner_name": "Test Owner",
        "tin": "",
        "website": "",
        "social_links": {
            "instagram": f"https://instagram.com/bron{RUN_ID}",
            "telegram": "",
        },
        "comments": "",
    }

    response = request(
        "POST",
        "/businesses/create",
        headers=OWNER_HEADERS,
        json=business_payload,
        expected=(200, 201),
        name="Create business",
    )

    data = get_json(response)

    print(
        "    Business create response:",
        data
    )

    BUSINESS_ID = get_id(
        response,
        "business_id"
    )

    if not BUSINESS_ID:

        print(
            "❌ BUSINESS_ID was not returned."
        )

        print(
            "    Full response:",
            data
        )

        return False

    print(
        f"    BUSINESS_ID = {BUSINESS_ID}"
    )

    request(
        "GET",
        "/businesses/",
        expected=(200,),
        name="Business list",
    )

    response = request(
        "GET",
        f"/businesses/{BUSINESS_ID}",
        expected=(200,),
        name="Business detail",
    )

    if response is not None and response.status_code == 200:
        body = response.json()
        if body.get("status") != "pending":
            print(f"    ⚠️  new business status is {body.get('status')!r}, expected 'pending'")
        if "owner_username" in body:
            print("    ⚠️  public detail exposes owner_username")

    response = request(
        "GET",
        "/businesses/my",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="My businesses (owner, includes pending)",
    )

    if response is not None and response.status_code == 200:
        mine = {b["id"]: b["status"] for b in response.json()}
        if mine.get(BUSINESS_ID) != "pending":
            print(f"    ⚠️  pending business missing from /businesses/my: {mine}")

    response = request(
        "GET",
        "/businesses/my",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="My businesses (customer, empty)",
    )

    if response is not None and response.status_code == 200 and response.json():
        print(f"    ⚠️  customer sees businesses: {response.json()}")

    request(
        "GET",
        "/businesses/my",
        expected=(401,),
        name="My businesses without token rejected",
    )

    request(
        "GET",
        "/businesses/search",
        params={"q": "BRON"},
        expected=(200,),
        name="Business search",
    )

    # Every request is a view now: no 24h dedup, the owner counts too
    views = []

    for headers, label in (
        (CUSTOMER_HEADERS, "customer, first"),
        (CUSTOMER_HEADERS, "customer, repeat"),
        (OWNER_HEADERS, "owner"),
        (None, "anonymous"),
    ):
        view = request(
            "POST",
            f"/businesses/{BUSINESS_ID}/view",
            headers=headers,
            expected=(200,),
            name=f"Business view ({label})",
        )

        if not is_ok(view):
            views = None
            continue

        body = view.json()
        check(f"View ({label}) is counted", body.get("counted") is True, body)

        if views is not None:
            expected_count = views[-1] + 1 if views else 1
            check(
                f"views_count is {expected_count} after the {label} view",
                body.get("views_count") == expected_count,
                body,
            )
            views.append(body.get("views_count"))

    request(
        "POST",
        "/businesses/999999999/view",
        expected=(404,),
        name="View of unknown business -> 404",
    )

    request(
        "GET",
        "/businesses/category/gym",
        expected=(200,),
        name="Business category",
    )

    response = request(
        "GET",
        f"/businesses/{BUSINESS_ID}/stats",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Business stats",
    )

    if is_ok(response) and views:
        check(
            f"Stats views_count equals {views[-1]} (all views counted)",
            response.json().get("views_count") == views[-1],
            response.json(),
        )

    request(
        "GET",
        f"/businesses/{BUSINESS_ID}/analytics",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Business analytics",
    )

    return True


# ============================================================
# STEP 3.1 — BUSINESS APPLICATION FORM
# ============================================================

def test_business_application():

    print_section("STEP 3.1 — BUSINESS APPLICATION FORM")

    full_name = f"BRON Test Applicant {RUN_ID}"

    # RUN_ID is hex, but the endpoint accepts digits only
    digits = f"{int(RUN_ID, 16) % 10 ** 7:07d}"
    phone = f"+998 90 {digits[:3]} {digits[3:5]} {digits[5:]}"

    response = request(
        "POST",
        "/business-applications/create",
        json={
            "full_name": full_name,
            "phone": phone,
        },
        expected=(201,),
        name="Application (anonymous, name + phone)",
    )

    if response is not None and response.status_code == 201:
        body = response.json()
        if body.get("phone") != f"+99890{digits}":
            print(f"    ⚠️  phone was not normalized: {body.get('phone')}")
        if body.get("status") != "new":
            print(f"    ⚠️  unexpected status: {body.get('status')}")

    request(
        "POST",
        "/business-applications/create",
        headers=CUSTOMER_HEADERS,
        json={
            "full_name": full_name,
            "phone": phone,
            "email": f"applicant{RUN_ID}@example.com",
            "social": f"@bron{RUN_ID}",
            "comment": "Automated BRON integration test.",
        },
        expected=(201,),
        name="Application (customer, all fields)",
    )

    request(
        "POST",
        "/business-applications/create",
        json={"full_name": full_name},
        expected=(422,),
        name="Application without phone rejected",
    )

    request(
        "POST",
        "/business-applications/create",
        json={"full_name": full_name, "phone": "call me"},
        expected=(422,),
        name="Application with invalid phone rejected",
    )

    request(
        "POST",
        "/business-applications/create",
        json={"full_name": full_name, "phone": phone, "email": "not-an-email"},
        expected=(422,),
        name="Application with invalid email rejected",
    )

    request(
        "POST",
        "/business-applications/create",
        json={"full_name": full_name, "phone": phone, "comment": "x" * 121},
        expected=(422,),
        name="Application with comment over 120 chars rejected",
    )

    # The form is rate-limited per IP, so test runs shouldn't use up the quota
    run_django_locally(
        "from core.models import BusinessApplication; "
        f"BusinessApplication.objects.filter(full_name='{full_name}').delete()"
    )


# ============================================================
# STEP 4 — BRANCHES
# ============================================================

def test_branch():

    global BRANCH_ID

    print_section("STEP 4 — BRANCHES")

    if not BUSINESS_ID:

        skip_test(
            "Create branch",
            "BUSINESS_ID unavailable"
        )

        return False

    payload = {
        "business_id": BUSINESS_ID,
        "name": "BRON Main Branch",
        "address": "Tashkent",
        "phone": f"+99894{RUN_ID[:7]}",
    }

    response = request(
        "POST",
        "/branches/create",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Create branch",
    )

    BRANCH_ID = get_id(
        response,
        "branch_id"
    )

    if BRANCH_ID:

        print(
            f"    BRANCH_ID = {BRANCH_ID}"
        )

        request(
            "GET",
            f"/branches/{BRANCH_ID}",
            expected=(200,),
            name="Branch detail",
        )

    else:
        print_response_body(response)

    request(
        "GET",
        "/branches/",
        expected=(200,),
        name="Branch list",
    )

    request(
        "GET",
        f"/branches/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business branches",
    )

    return BRANCH_ID is not None


# ============================================================
# STEP 5 — SERVICES
# ============================================================

def test_services():

    global SERVICE_ID

    print_section("STEP 5 — SERVICES")

    if not BUSINESS_ID:

        skip_test(
            "Create service",
            "BUSINESS_ID unavailable"
        )

        return False

    payload = {
        "business_id": BUSINESS_ID,
        "title": "BRON Test Service",
        "description": "Automated API test service",
        "category": "Diagnostics",
        "duration": 60,
        "price": "350000.00",
    }

    response = request(
        "POST",
        "/services/create",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Create service",
    )

    SERVICE_ID = get_id(
        response,
        "service_id"
    )

    if SERVICE_ID:

        print(
            f"    SERVICE_ID = {SERVICE_ID}"
        )

        check(
            "Service without schedule has availability []",
            get_json(response).get("availability") == [],
            get_json(response).get("availability"),
        )

        request(
            "GET",
            f"/services/{SERVICE_ID}",
            expected=(200,),
            name="Service detail",
        )

    else:
        print_response_body(response)

    # --------------------------------------------------------
    # AVAILABILITY FORMAT VALIDATION
    # --------------------------------------------------------

    day = BOOKING_DATE.isoformat()

    for availability, label in (
        ([{"date": BOOKING_DATE.strftime("%Y/%m/%d"), "times": ["10:00"]}], "date not YYYY-MM-DD"),
        ([{"date": day, "times": ["7:00"]}], "time not HH:MM"),
        ([{"date": day, "times": ["24:00"]}], "time 24:00"),
        ([{"date": day, "times": ["10:00"]}, {"date": day, "times": ["11:00"]}], "same date twice"),
        ([{"date": day}], "entry without times"),
    ):
        request(
            "POST",
            "/services/create",
            headers=OWNER_HEADERS,
            json={**payload, "availability": availability},
            expected=(422,),
            name=f"Availability rejected: {label}",
        )

    response = request(
        "POST",
        "/services/create",
        headers=OWNER_HEADERS,
        json={
            **payload,
            "duration": 45,
            "availability": [{"date": day, "times": ["23:30"]}],
        },
        expected=(400,),
        name="Availability slot ending after 23:59 -> 400",
    )

    check_detail(
        "23:59 error message",
        response,
        f"Slot at 23:30 on {day} would end after 23:59",
    )

    request(
        "GET",
        "/services/",
        expected=(200,),
        name="Service list",
    )

    request(
        "GET",
        "/services/categories",
        expected=(200,),
        name="Service categories",
    )

    request(
        "GET",
        "/services/search",
        params={"q": "BRON"},
        expected=(200,),
        name="Service search",
    )

    request(
        "GET",
        f"/services/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business services",
    )

    return SERVICE_ID is not None


# ============================================================
# STEP 6 — PRODUCTS
# ============================================================

def test_products():

    global PRODUCT_ID

    print_section("STEP 6 — PRODUCTS")

    if not BUSINESS_ID:

        skip_test(
            "Create product",
            "BUSINESS_ID unavailable"
        )

        return False

    payload = {
        "business_id": BUSINESS_ID,
        "name": "BRON Test Product",
        "description": "Automated testing product",
        "price": "95000.00",
    }

    response = request(
        "POST",
        "/products/create",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Create product",
    )

    PRODUCT_ID = get_id(
        response,
        "product_id"
    )

    if PRODUCT_ID:

        print(
            f"    PRODUCT_ID = {PRODUCT_ID}"
        )

        request(
            "GET",
            f"/products/{PRODUCT_ID}",
            expected=(200,),
            name="Product detail",
        )

    else:
        print_response_body(response)

    request(
        "GET",
        "/products/",
        expected=(200,),
        name="Product list",
    )

    request(
        "GET",
        "/products/search",
        params={"q": "BRON"},
        expected=(200,),
        name="Product search",
    )

    request(
        "GET",
        f"/products/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business products",
    )

    return PRODUCT_ID is not None


# ============================================================
# STEP 6.1 — PRODUCT PHOTO
# ============================================================

def find_by_id(items, obj_id):
    if not isinstance(items, list):
        return None
    return next((i for i in items if isinstance(i, dict) and i.get("id") == obj_id), None)


def test_product_image():

    print_section("STEP 6.1 — PRODUCT PHOTO")

    if not PRODUCT_ID:

        skip_test(
            "Product photo",
            "PRODUCT_ID unavailable"
        )

        return

    endpoint = f"/products/{PRODUCT_ID}/image"

    response = request(
        "POST",
        endpoint,
        headers=OWNER_HEADERS,
        files=image_upload("red", "PNG"),
        expected=(200,),
        name="Owner uploads product photo (PNG)",
    )

    first_url = get_json(response).get("image")

    if is_ok(response):
        check(
            "Product image is an absolute /media/ URL",
            is_absolute_url(first_url) and "/media/" in first_url,
            first_url,
        )
        check(
            "Uploaded photo is served",
            media_status(first_url) == 200,
            media_status(first_url),
        )

    response = request(
        "GET",
        f"/products/{PRODUCT_ID}",
        expected=(200,),
        name="Product detail with photo",
    )

    if is_ok(response):
        check(
            "Detail returns the same absolute URL",
            response.json().get("image") == first_url,
            response.json().get("image"),
        )

    for endpoint_list, label in (
        (f"/products/business/{BUSINESS_ID}", "Business products"),
        ("/products/", "Product list"),
    ):
        response = request(
            "GET",
            endpoint_list,
            expected=(200,),
            name=f"{label} with photo",
        )

        if is_ok(response):
            item = find_by_id(response.json(), PRODUCT_ID)
            check(
                f"{label}: image is absolute",
                item is not None and item.get("image") == first_url,
                item,
            )

    response = request(
        "POST",
        endpoint,
        headers=OWNER_HEADERS,
        files=image_upload("blue", "JPEG"),
        expected=(200,),
        name="Owner replaces photo (JPEG)",
    )

    second_url = get_json(response).get("image")

    if is_ok(response):
        check(
            "Replaced photo has a new URL",
            is_absolute_url(second_url) and second_url != first_url,
            second_url,
        )
        check(
            "Old photo file was deleted",
            media_status(first_url) == 404,
            media_status(first_url),
        )

    request(
        "POST",
        endpoint,
        headers=OWNER_HEADERS,
        files=image_upload("green", "WEBP"),
        expected=(200,),
        name="Owner uploads WEBP photo",
    )

    request(
        "POST",
        endpoint,
        headers=CUSTOMER_HEADERS,
        files=image_upload("red", "PNG"),
        expected=(403,),
        name="Customer cannot upload product photo",
    )

    request(
        "POST",
        endpoint,
        files=image_upload("red", "PNG"),
        expected=(401,),
        name="Photo upload without token rejected",
    )

    response = request(
        "POST",
        endpoint,
        headers=OWNER_HEADERS,
        files={"image": ("notes.txt", b"not an image", "text/plain")},
        expected=(400,),
        name="Non-image file rejected",
    )

    check_detail(
        "Wrong type message",
        response,
        "Only JPEG, PNG or WEBP images are allowed",
    )

    response = request(
        "POST",
        endpoint,
        headers=OWNER_HEADERS,
        files={"image": ("big.png", b"\0" * (5 * 1024 * 1024 + 1), "image/png")},
        expected=(400,),
        name="Photo over 5 MB rejected",
    )

    check_detail(
        "Too large message",
        response,
        "Image must be smaller than 5 MB",
    )

    request(
        "POST",
        endpoint,
        headers=OWNER_HEADERS,
        files=image_upload("red", "PNG", field="photo"),
        expected=(422,),
        name="Upload without image field rejected",
    )

    request(
        "POST",
        "/products/999999999/image",
        headers=OWNER_HEADERS,
        files=image_upload("red", "PNG"),
        expected=(404,),
        name="Photo for unknown product -> 404",
    )

    request(
        "DELETE",
        endpoint,
        headers=CUSTOMER_HEADERS,
        expected=(403,),
        name="Customer cannot delete product photo",
    )

    current = get_json(raw("GET", f"/products/{PRODUCT_ID}")).get("image")

    response = request(
        "DELETE",
        endpoint,
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Owner deletes product photo",
    )

    if is_ok(response):
        check(
            "Product image is null after delete",
            response.json().get("image") is None,
            response.json().get("image"),
        )
        check(
            "Deleted photo file is gone",
            media_status(current) == 404,
            media_status(current),
        )

    request(
        "DELETE",
        endpoint,
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Deleting a missing photo is safe",
    )


# ============================================================
# STEP 7 — STAFF
# ============================================================

def test_staff():

    global STAFF_ID

    print_section("STEP 7 — STAFF")

    if not BUSINESS_ID:

        skip_test(
            "Create staff",
            "BUSINESS_ID unavailable"
        )

        return False

    payload = {
        "business_id": BUSINESS_ID,
        "full_name": "BRON Test Employee",
        "position": "Test Specialist",
        "phone": f"+99895{RUN_ID[:7]}",
    }

    response = request(
        "POST",
        "/staff/create",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Create staff",
    )

    STAFF_ID = get_id(
        response,
        "staff_id"
    )

    if STAFF_ID:

        print(
            f"    STAFF_ID = {STAFF_ID}"
        )

        request(
            "GET",
            f"/staff/{STAFF_ID}",
            expected=(200,),
            name="Staff detail",
        )

        request(
            "GET",
            f"/staff/{STAFF_ID}/schedule",
            expected=(200,),
            name="Staff schedule",
        )

        request(
            "GET",
            f"/staff/{STAFF_ID}/bookings",
            headers=OWNER_HEADERS,
            expected=(200,),
            name="Staff bookings",
        )

    else:
        print_response_body(response)

    request(
        "GET",
        "/staff/",
        expected=(200,),
        name="Staff list",
    )

    request(
        "GET",
        f"/staff/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business staff",
    )

    return STAFF_ID is not None


# ============================================================
# STEP 8 — WORKING HOURS
# ============================================================

def test_working_hours():

    global WORKING_HOURS_ID

    print_section("STEP 8 — WORKING HOURS")

    if not BUSINESS_ID:

        skip_test(
            "Working hours",
            "BUSINESS_ID unavailable"
        )

        return

    payload = {
        "business_id": BUSINESS_ID,
        "day_of_week": date.today().weekday(),
        "open_time": "08:00:00",
        "close_time": "22:00:00",
        "is_closed": False,
    }

    response = request(
        "POST",
        "/working-hours/create",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Create working hours",
    )

    WORKING_HOURS_ID = get_id(
        response,
        "working_hours_id"
    )

    if WORKING_HOURS_ID:

        print(
            f"    WORKING_HOURS_ID = {WORKING_HOURS_ID}"
        )

        request(
            "GET",
            f"/working-hours/{WORKING_HOURS_ID}",
            expected=(200,),
            name="Working hours detail",
        )

    request(
        "GET",
        f"/working-hours/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business schedule",
    )

    request(
        "GET",
        f"/working-hours/today/{BUSINESS_ID}",
        expected=(200,),
        name="Today's schedule",
    )


# ============================================================
# STEP 9 — BLOCKED DATES
# ============================================================

def test_blocked_dates():

    global BLOCKED_DATE_ID

    print_section("STEP 9 — BLOCKED DATES")

    if not BUSINESS_ID:

        skip_test(
            "Blocked dates",
            "BUSINESS_ID unavailable"
        )

        return

    blocked_date = BLOCKED_DATE

    payload = {
        "business_id": BUSINESS_ID,
        "date": blocked_date.isoformat(),
        "reason": "Automated API testing block",
    }

    response = request(
        "POST",
        "/blocked-dates/create",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Create blocked date",
    )

    BLOCKED_DATE_ID = get_id(
        response,
        "blocked_date_id"
    )

    if BLOCKED_DATE_ID:
        print(
            f"    BLOCKED_DATE_ID = {BLOCKED_DATE_ID}"
        )

    request(
        "GET",
        f"/blocked-dates/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business blocked dates",
    )

    response = request(
        "GET",
        "/blocked-dates/check",
        params={
            "business_id": BUSINESS_ID,
            "date": blocked_date.isoformat(),
        },
        expected=(200,),
        name="Check blocked date",
    )

    if is_ok(response):
        check(
            "Blocked date: is_blocked true with reason",
            response.json() == {
                "business_id": BUSINESS_ID,
                "date": blocked_date.isoformat(),
                "is_blocked": True,
                "reason": "Automated API testing block",
            },
            response.json(),
        )

    free_date = blocked_date + timedelta(days=1)

    response = request(
        "GET",
        "/blocked-dates/check",
        params={
            "business_id": BUSINESS_ID,
            "date": free_date.isoformat(),
        },
        expected=(200,),
        name="Check free date",
    )

    if is_ok(response):
        check(
            "Free date: is_blocked false, reason null",
            response.json() == {
                "business_id": BUSINESS_ID,
                "date": free_date.isoformat(),
                "is_blocked": False,
                "reason": None,
            },
            response.json(),
        )

    response = request(
        "GET",
        "/blocked-dates/check",
        params={
            "business_id": 999999999,
            "date": blocked_date.isoformat(),
        },
        expected=(200,),
        name="Check date of unknown business",
    )

    if is_ok(response):
        check(
            "Unknown business: is_blocked false",
            response.json().get("is_blocked") is False,
            response.json(),
        )

    request(
        "GET",
        "/blocked-dates/check",
        params={
            "business_id": BUSINESS_ID,
            "target_date": blocked_date.isoformat(),
        },
        expected=(422,),
        name="Old target_date parameter rejected",
    )

    request(
        "GET",
        "/blocked-dates/check",
        params={
            "business_id": BUSINESS_ID,
            "date": "2026-13-01",
        },
        expected=(422,),
        name="Malformed date rejected",
    )

    if BLOCKED_DATE_ID:

        request(
            "GET",
            f"/blocked-dates/{BLOCKED_DATE_ID}",
            expected=(200,),
            name="Blocked date detail",
        )


# ============================================================
# STEP 10 — BOOKINGS
# ============================================================

def activate_business_locally():
    """
    New businesses need admin approval (is_active=True) before they accept
    bookings. There is no API for that, so when testing against a local server
    we flip the flag through manage.py.
    """
    return run_django_locally(
        f"from core.models import Business; Business.objects.filter(id={BUSINESS_ID}).update(is_active=True)"
    )


SERVICE_TITLE = "BRON Test Service"
SERVICE_PRICE = 350000.0
PRODUCT_NAME = "BRON Test Product"
PRODUCT_PRICE = 95000.0


def order_lines(body):
    """{(kind, id): (name, price, quantity)} from the items of a booking."""
    items = body.get("items") if isinstance(body, dict) else None

    if not isinstance(items, list):
        return None

    return {
        (item.get("kind"), item.get("id")): (item.get("name"), item.get("price"), item.get("quantity"))
        for item in items
    }


def check_order(label, body, expected_lines, expected_total):
    """Items and total_price of a booking body, priced by the server."""
    lines = order_lines(body)
    items = body.get("items") if isinstance(body, dict) else None

    check(
        f"{label}: items",
        lines == expected_lines and len(items or []) == len(expected_lines),
        items,
    )

    check(
        f"{label}: total_price {expected_total:.2f}",
        isinstance(body, dict) and body.get("total_price") == expected_total,
        body.get("total_price") if isinstance(body, dict) else body,
    )


def main_order_lines(product_quantity):
    lines = {("service", SERVICE_ID): (SERVICE_TITLE, SERVICE_PRICE, 1)}

    if product_quantity:
        lines[("product", PRODUCT_ID)] = (PRODUCT_NAME, PRODUCT_PRICE, product_quantity)

    return lines


def cancel_booking(booking_id, name):
    if booking_id:
        request(
            "PATCH",
            f"/bookings/{booking_id}/cancel",
            headers=CUSTOMER_HEADERS,
            expected=(200,),
            name=name,
        )


def create_foreign_business():
    """
    A second business owned by the customer (category "other") with a
    branch, service, product and staff member. Its ids must be rejected
    together with BUSINESS_ID.
    """
    if FOREIGN:
        return all(FOREIGN.values())

    response = request(
        "POST",
        "/businesses/create",
        headers=CUSTOMER_HEADERS,
        json={
            "name": f"BRON Foreign Business {RUN_ID}",
            "description": "Second business for foreign-id checks.",
            "category_id": OTHER_CATEGORY_ID or 1,
            "address": "Samarkand",
            "phone": f"+99897{RUN_ID[:7]}",
            "email": f"foreign{RUN_ID}@example.com",
            "owner_name": "Foreign Owner",
        },
        expected=(200, 201),
        name="Foreign business (customer-owned)",
    )

    FOREIGN["business_id"] = get_id(response)

    if not FOREIGN["business_id"]:
        return False

    if OTHER_CATEGORY_ID:
        # /businesses/create returns only the id
        detail = get_json(raw("GET", f"/businesses/{FOREIGN['business_id']}"))
        category = detail.get("category") or {}
        check(
            'Business can use category "other"',
            category.get("slug") == "other",
            category,
        )

    business_id = FOREIGN["business_id"]

    for key, endpoint, payload in (
        ("branch_id", "/branches/create", {
            "business_id": business_id,
            "name": "Foreign Branch",
            "address": "Samarkand",
            "phone": f"+99898{RUN_ID[:7]}",
        }),
        ("service_id", "/services/create", {
            "business_id": business_id,
            "title": "Foreign Service",
            "description": "Foreign service",
            "category": "Diagnostics",
            "duration": 60,
            "price": "1000.00",
        }),
        ("product_id", "/products/create", {
            "business_id": business_id,
            "name": "Foreign Product",
            # Omitting description gives 500 (NOT NULL in the model)
            "description": "Foreign product",
            "price": "1000.00",
        }),
        ("staff_id", "/staff/create", {
            "business_id": business_id,
            "full_name": "Foreign Employee",
            "position": "Specialist",
            "phone": f"+99899{RUN_ID[:7]}",
        }),
    ):
        response = request(
            "POST",
            endpoint,
            headers=CUSTOMER_HEADERS,
            json=payload,
            expected=(200, 201),
            name=f"Foreign {key[:-3]}",
        )

        FOREIGN[key] = get_id(response)

    return all(FOREIGN.values())


def test_booking():

    global BOOKING_ID, BUSINESS_ACTIVE

    print_section("STEP 10 — BOOKINGS")

    if not all([
        BUSINESS_ID,
        BRANCH_ID,
        SERVICE_ID,
    ]):

        skip_test(
            "Booking tests",
            "Required related objects missing"
        )

        return False

    booking_date = BOOKING_DATE

    slots_params = {
        "business_id": BUSINESS_ID,
        "service_id": SERVICE_ID,
        "branch_id": BRANCH_ID,
        "date": booking_date.isoformat(),
    }

    # --------------------------------------------------------
    # NOT APPROVED YET: NO SLOTS
    # --------------------------------------------------------

    response = request(
        "GET",
        "/bookings/available-slots",
        params=slots_params,
        expected=(200,),
        name="Available slots (business not approved)",
    )

    if is_ok(response):
        check(
            "Not approved business has no slots",
            response.json().get("slots") == [],
            response.json(),
        )

    if not activate_business_locally():

        skip_test(
            "Booking tests",
            "Business must be approved in admin (is_active=True) before booking"
        )

        return False

    BUSINESS_ACTIVE = True

    response = request(
        "GET",
        "/businesses/my",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="My businesses after approval",
    )

    if response is not None and response.status_code == 200:
        mine = {b["id"]: b["status"] for b in response.json()}
        if mine.get(BUSINESS_ID) != "approved":
            print(f"    ⚠️  approved business has status {mine.get(BUSINESS_ID)!r}")

    create_foreign_business()

    # --------------------------------------------------------
    # BOOKING WITH ITEMS
    # name/price sent by the client must be ignored
    # --------------------------------------------------------

    product_quantity = 2 if PRODUCT_ID else 0

    payload = {
        "business_id": BUSINESS_ID,
        "service_id": SERVICE_ID,
        "branch_id": BRANCH_ID,
        "staff_id": STAFF_ID,
        "booking_date": booking_date.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "guest_count": 1,
        "items": (
            [{
                "id": PRODUCT_ID,
                "kind": "product",
                "quantity": 2,
                "name": "Free product",
                "price": "1.00",
            }]
            if PRODUCT_ID
            else []
        ),
    }

    response = request(
        "POST",
        "/bookings/create",
        headers=CUSTOMER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Customer creates booking (product x2, fake price)",
    )

    BOOKING_ID = get_id(
        response,
        "booking_id"
    )

    if not BOOKING_ID:

        print(
            "❌ BOOKING_ID was not returned."
        )

        print_response_body(response)

        return False

    print(
        f"    BOOKING_ID = {BOOKING_ID}"
    )

    expected_lines = main_order_lines(product_quantity)
    expected_total = SERVICE_PRICE + PRODUCT_PRICE * product_quantity

    check_order("Created booking", get_json(response), expected_lines, expected_total)

    response = request(
        "GET",
        "/bookings/my",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Customer booking list",
    )

    if is_ok(response):
        check_order(
            "My bookings",
            find_by_id(response.json(), BOOKING_ID) or {},
            expected_lines,
            expected_total,
        )

    response = request(
        "GET",
        f"/bookings/{BOOKING_ID}",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Booking detail",
    )

    if is_ok(response):
        check_order("Booking detail", response.json(), expected_lines, expected_total)

    response = request(
        "GET",
        f"/bookings/business/{BUSINESS_ID}",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Business bookings",
    )

    if is_ok(response):
        check_order(
            "Business bookings",
            find_by_id(response.json(), BOOKING_ID) or {},
            expected_lines,
            expected_total,
        )

    if STAFF_ID:

        request(
            "GET",
            f"/bookings/staff/{STAFF_ID}",
            headers=OWNER_HEADERS,
            expected=(200,),
            name="Staff booking list",
        )

    test_available_slots(slots_params)

    test_booking_items()

    test_booking_reschedule(booking_date)

    return True


def test_available_slots(slots_params):

    print_section("STEP 10.0 — AVAILABLE SLOTS")

    # Working hours 08:00-22:00 and a 60-minute service: 14 hourly slots,
    # 10:00 is taken by the booking above (capacity 1)
    hourly = [f"{hour:02d}:00" for hour in range(8, 22)]

    for staff_id, label in ((None, "any staff"), (STAFF_ID, "with staff_id")):

        if label == "with staff_id" and not STAFF_ID:
            continue

        params = dict(slots_params)
        if staff_id:
            params["staff_id"] = staff_id

        response = request(
            "GET",
            "/bookings/available-slots",
            params=params,
            expected=(200,),
            name=f"Available slots ({label})",
        )

        if not is_ok(response):
            continue

        body = response.json()

        check(
            f"Slots ({label}): request context echoed",
            {key: body.get(key) for key in (
                "business_id", "service_id", "branch_id", "staff_id",
                "date", "duration", "capacity",
            )} == {
                "business_id": BUSINESS_ID,
                "service_id": SERVICE_ID,
                "branch_id": BRANCH_ID,
                "staff_id": staff_id,
                "date": slots_params["date"],
                "duration": 60,
                "capacity": 1,
            },
            {key: value for key, value in body.items() if key != "slots"},
        )

        slots = body.get("slots") or []
        by_start = {slot.get("start_time"): slot for slot in slots}

        check(
            f"Slots ({label}): hourly 08:00-21:00 from working hours",
            [slot.get("start_time") for slot in slots] == hourly,
            [slot.get("start_time") for slot in slots],
        )

        check(
            f"Slots ({label}): 10:00 is booked",
            by_start.get("10:00") == {
                "start_time": "10:00",
                "end_time": "11:00",
                "is_available": False,
                "available_spots": 0,
            },
            by_start.get("10:00"),
        )

        check(
            f"Slots ({label}): 09:00 is free",
            by_start.get("09:00") == {
                "start_time": "09:00",
                "end_time": "10:00",
                "is_available": True,
                "available_spots": 1,
            },
            by_start.get("09:00"),
        )

    for key, message in (
        ("service_id", "Service not found"),
        ("branch_id", "Branch not found"),
        ("staff_id", "Staff not found"),
    ):
        foreign_id = FOREIGN.get(key)

        if not foreign_id:
            continue

        response = request(
            "GET",
            "/bookings/available-slots",
            params={**slots_params, key: foreign_id},
            expected=(404,),
            name=f"Available slots: foreign {key[:-3]} -> 404",
        )

        check_detail(f"Foreign {key[:-3]} message", response, message)

    response = request(
        "GET",
        "/bookings/available-slots",
        params={**slots_params, "business_id": 999999999},
        expected=(404,),
        name="Available slots: unknown business -> 404",
    )

    check_detail("Unknown business message", response, "Business not found")

    request(
        "GET",
        "/bookings/available-slots",
        params={
            "business_id": BUSINESS_ID,
            "staff_id": STAFF_ID,
            "target_date": slots_params["date"],
        },
        expected=(422,),
        name="Available slots: old parameters rejected",
    )

    request(
        "GET",
        "/bookings/available-slots",
        params={key: value for key, value in slots_params.items() if key != "branch_id"},
        expected=(422,),
        name="Available slots: branch_id required",
    )


def test_booking_items():

    print_section("STEP 10.1 — BOOKING ITEMS")

    if not PRODUCT_ID:

        skip_test(
            "Booking items",
            "PRODUCT_ID unavailable"
        )

        return

    base = {
        "business_id": BUSINESS_ID,
        "service_id": SERVICE_ID,
        "branch_id": BRANCH_ID,
        "booking_date": BOOKING_DATE.isoformat(),
        "start_time": "16:00",
        "end_time": "17:00",
        "guest_count": 1,
    }

    # --------------------------------------------------------
    # DUPLICATE LINES ARE MERGED
    # --------------------------------------------------------

    response = request(
        "POST",
        "/bookings/create",
        headers=CUSTOMER_HEADERS,
        json={
            **base,
            "items": [
                {"id": PRODUCT_ID, "kind": "product", "quantity": 1},
                {"id": SERVICE_ID, "kind": "service", "quantity": 1, "price": "0"},
                {"id": PRODUCT_ID, "kind": "product", "quantity": 2, "price": "1"},
            ],
        },
        expected=(200,),
        name="Booking with duplicate item lines",
    )

    if is_ok(response):
        check_order(
            "Duplicate lines merged",
            response.json(),
            main_order_lines(3),
            SERVICE_PRICE + PRODUCT_PRICE * 3,
        )
        cancel_booking(response.json().get("id"), "Cancel duplicate-lines booking")

    # --------------------------------------------------------
    # LEGACY product_ids (only when items is empty)
    # --------------------------------------------------------

    response = request(
        "POST",
        "/bookings/create",
        headers=CUSTOMER_HEADERS,
        json={**base, "product_ids": [PRODUCT_ID, 999999999]},
        expected=(200,),
        name="Legacy product_ids (unknown id skipped)",
    )

    if is_ok(response):
        check_order(
            "Legacy product_ids",
            response.json(),
            main_order_lines(1),
            SERVICE_PRICE + PRODUCT_PRICE,
        )
        cancel_booking(response.json().get("id"), "Cancel legacy product_ids booking")

    response = request(
        "POST",
        "/bookings/create",
        headers=CUSTOMER_HEADERS,
        json={
            **base,
            "items": [{"id": SERVICE_ID, "kind": "service", "quantity": 1}],
            "product_ids": [PRODUCT_ID],
        },
        expected=(200,),
        name="items given: product_ids ignored",
    )

    if is_ok(response):
        check_order(
            "product_ids ignored with items",
            response.json(),
            main_order_lines(0),
            SERVICE_PRICE,
        )
        cancel_booking(response.json().get("id"), "Cancel items-only booking")

    # --------------------------------------------------------
    # REJECTED ITEMS: nothing may be booked
    # --------------------------------------------------------

    my_before = get_json(raw("GET", "/bookings/my", headers=CUSTOMER_HEADERS))

    response = request(
        "POST",
        "/products/create",
        headers=OWNER_HEADERS,
        json={
            "business_id": BUSINESS_ID,
            "name": "BRON Inactive Product",
            "description": "Deactivated right away",
            "price": "5000.00",
        },
        expected=(200,),
        name="Create product to deactivate",
    )

    inactive_product_id = get_id(response)

    if inactive_product_id:
        request(
            "PUT",
            f"/products/{inactive_product_id}",
            headers=OWNER_HEADERS,
            json={"is_active": False},
            expected=(200,),
            name="Deactivate product",
        )

    rejected = [
        (
            [{"id": 999999999, "kind": "product", "quantity": 1}],
            "Item not found: product 999999999",
            "Unknown product",
        ),
    ]

    if inactive_product_id:
        rejected.append((
            [{"id": inactive_product_id, "kind": "product", "quantity": 1}],
            f"Item not found: product {inactive_product_id}",
            "Inactive product",
        ))

    if FOREIGN.get("product_id"):
        rejected.append((
            [{"id": FOREIGN["product_id"], "kind": "product", "quantity": 1}],
            f"Item not found: product {FOREIGN['product_id']}",
            "Product of another business",
        ))

    if FOREIGN.get("service_id"):
        rejected.append((
            [{"id": FOREIGN["service_id"], "kind": "service", "quantity": 1}],
            f"Item not found: service {FOREIGN['service_id']}",
            "Service of another business",
        ))

    rejected.append((
        [
            {"id": PRODUCT_ID, "kind": "product", "quantity": 60},
            {"id": PRODUCT_ID, "kind": "product", "quantity": 60},
        ],
        f"Quantity of product {PRODUCT_ID} must be at most 100",
        "Merged quantity over 100",
    ))

    for items, message, label in rejected:
        response = request(
            "POST",
            "/bookings/create",
            headers=CUSTOMER_HEADERS,
            json={**base, "start_time": "18:00", "end_time": "19:00", "items": items},
            expected=(400,),
            name=f"{label} -> 400",
        )

        check_detail(f"{label} message", response, message)

    for item, label in (
        ({"id": PRODUCT_ID, "kind": "product", "quantity": 101}, "quantity 101"),
        ({"id": PRODUCT_ID, "kind": "product", "quantity": 0}, "quantity 0"),
        ({"id": PRODUCT_ID, "kind": "gift", "quantity": 1}, "unknown kind"),
        ({"kind": "product", "quantity": 1}, "item without id"),
    ):
        request(
            "POST",
            "/bookings/create",
            headers=CUSTOMER_HEADERS,
            json={**base, "start_time": "18:00", "end_time": "19:00", "items": [item]},
            expected=(422,),
            name=f"Item with {label} -> 422",
        )

    my_after = get_json(raw("GET", "/bookings/my", headers=CUSTOMER_HEADERS))

    check(
        "Rejected orders created no bookings",
        isinstance(my_before, list) and isinstance(my_after, list) and len(my_after) == len(my_before),
        f"{len(my_before or [])} -> {len(my_after or [])}",
    )


def test_booking_reschedule(booking_date):

    print_section("STEP 10.2 — BOOKING RESCHEDULE")

    response = request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        headers=CUSTOMER_HEADERS,
        json={
            "booking_date": booking_date.isoformat(),
            "start_time": "12:00",
            "end_time": "13:00",
        },
        expected=(200,),
        name="Customer reschedules booking",
    )

    if response is not None and response.status_code == 200:
        body = response.json()
        if body.get("start_time") != "12:00:00":
            print(f"    ⚠️  unexpected start_time after reschedule: {body.get('start_time')}")

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        headers=CUSTOMER_HEADERS,
        json={
            "booking_date": (date.today() - timedelta(days=1)).isoformat(),
            "start_time": "12:00",
            "end_time": "13:00",
        },
        expected=(400,),
        name="Reschedule to the past rejected",
    )

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        headers=CUSTOMER_HEADERS,
        json={
            "booking_date": booking_date.isoformat(),
            "start_time": "13:00",
            "end_time": "12:00",
        },
        expected=(400,),
        name="Reschedule with end before start rejected",
    )

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        headers=CUSTOMER_HEADERS,
        json={
            "booking_date": booking_date.isoformat(),
            "start_time": "05:00",
            "end_time": "06:00",
        },
        expected=(400,),
        name="Reschedule outside working hours rejected",
    )

    # Occupy 14:00 with a second booking, then try to move the first one there
    blocker = request(
        "POST",
        "/bookings/create",
        headers=CUSTOMER_HEADERS,
        json={
            "business_id": BUSINESS_ID,
            "service_id": SERVICE_ID,
            "branch_id": BRANCH_ID,
            "staff_id": STAFF_ID,
            "booking_date": booking_date.isoformat(),
            "start_time": "14:00",
            "end_time": "15:00",
            "guest_count": 1,
            "product_ids": [],
        },
        expected=(200,),
        name="Second booking occupies 14:00",
    )

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        headers=CUSTOMER_HEADERS,
        json={
            "booking_date": booking_date.isoformat(),
            "start_time": "14:00",
            "end_time": "15:00",
        },
        expected=(409,),
        name="Reschedule into taken slot -> 409",
    )

    if blocker is not None and blocker.status_code == 200:
        request(
            "PATCH",
            f"/bookings/{blocker.json()['id']}/cancel",
            headers=CUSTOMER_HEADERS,
            expected=(200,),
            name="Cancel second booking",
        )

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        expected=(401,),
        json={
            "booking_date": booking_date.isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
        },
        name="Reschedule without token rejected",
    )

    # Move back so the later steps work with the original time
    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/reschedule",
        headers=OWNER_HEADERS,
        json={
            "booking_date": booking_date.isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
        },
        expected=(200,),
        name="Owner reschedules booking back",
    )


# ============================================================
# STEP 10.3 — SERVICE SCHEDULE (availability)
# ============================================================

def slot_pairs(body):
    slots = body.get("slots") if isinstance(body, dict) else None
    return [(slot.get("start_time"), slot.get("end_time")) for slot in slots or []]


def test_service_schedule():

    global SCHEDULED_SERVICE_ID

    print_section("STEP 10.3 — SERVICE SCHEDULE (availability)")

    if not (BUSINESS_ACTIVE and BRANCH_ID):

        skip_test(
            "Service schedule",
            "Approved business with a branch unavailable"
        )

        return

    day = BOOKING_DATE
    day_off = day + timedelta(days=1)
    unlisted = day + timedelta(days=2)
    blocked = BLOCKED_DATE

    # Working hours of `day` are 08:00-22:00: 07:00 and 22:30 are outside
    # them and must still be offered, since the schedule replaces them
    expected_schedule = [
        {"date": day.isoformat(), "times": ["07:00", "10:30", "22:30"]},
        {"date": day_off.isoformat(), "times": []},
        {"date": blocked.isoformat(), "times": ["10:00"]},
    ]
    expected_slots = [("07:00", "07:45"), ("10:30", "11:15"), ("22:30", "23:15")]

    response = request(
        "POST",
        "/services/create",
        headers=OWNER_HEADERS,
        json={
            "business_id": BUSINESS_ID,
            "title": "BRON Scheduled Service",
            "description": "Service bookable only at listed times",
            "category": "Diagnostics",
            "duration": 45,
            "price": "120000.00",
            "availability": [
                {"date": blocked.isoformat(), "times": ["10:00"]},
                {"date": day.isoformat(), "times": ["22:30", "07:00", "10:30", "07:00"]},
                {"date": day_off.isoformat(), "times": []},
            ],
        },
        expected=(200,),
        name="Create service with own schedule",
    )

    SCHEDULED_SERVICE_ID = get_id(response)

    if not SCHEDULED_SERVICE_ID:
        return

    print(f"    SCHEDULED_SERVICE_ID = {SCHEDULED_SERVICE_ID}")

    service_endpoint = f"/services/{SCHEDULED_SERVICE_ID}"

    check(
        "Schedule stored sorted and de-duplicated",
        get_json(response).get("availability") == expected_schedule,
        get_json(response).get("availability"),
    )

    response = request(
        "GET",
        service_endpoint,
        expected=(200,),
        name="Scheduled service detail",
    )

    if is_ok(response):
        check(
            "Detail returns the schedule",
            response.json().get("availability") == expected_schedule,
            response.json().get("availability"),
        )

    response = request(
        "GET",
        f"/services/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business services with availability",
    )

    if is_ok(response):
        scheduled = find_by_id(response.json(), SCHEDULED_SERVICE_ID) or {}
        plain = find_by_id(response.json(), SERVICE_ID) or {}
        check(
            "List: schedule for scheduled service, [] for plain one",
            scheduled.get("availability") == expected_schedule
            and plain.get("availability") == [],
            {"scheduled": scheduled.get("availability"), "plain": plain.get("availability")},
        )

    # --------------------------------------------------------
    # SLOTS FOLLOW THE SCHEDULE
    # --------------------------------------------------------

    def availability(target, name):
        return request(
            "GET",
            f"{service_endpoint}/availability",
            params={"date": target.isoformat()},
            expected=(200,),
            name=name,
        )

    response = availability(day, "Availability on scheduled date")

    if is_ok(response):
        check(
            "Only scheduled times, 45-minute slots, working hours ignored",
            slot_pairs(response.json()) == expected_slots
            and all(slot.get("available_spots") == 1 for slot in response.json().get("slots")),
            response.json().get("slots"),
        )

    for target, label in (
        (day_off, "day off (empty times)"),
        (unlisted, "date not in schedule"),
        (blocked, "blocked date in schedule"),
    ):
        response = availability(target, f"Availability on {label}")

        if is_ok(response):
            check(
                f"No slots on {label}",
                response.json().get("slots") == [],
                response.json().get("slots"),
            )

    def available_dates(name):
        return request(
            "GET",
            f"{service_endpoint}/available-dates",
            params={"days": 40},
            expected=(200,),
            name=name,
        )

    response = available_dates("Available dates of scheduled service")

    if is_ok(response):
        check(
            "Only the scheduled date, with 3 free slots",
            response.json() == [{"date": day.isoformat(), "free_slots": 3}],
            response.json(),
        )

    response = request(
        "GET",
        "/bookings/available-slots",
        params={
            "business_id": BUSINESS_ID,
            "service_id": SCHEDULED_SERVICE_ID,
            "branch_id": BRANCH_ID,
            "date": day.isoformat(),
        },
        expected=(200,),
        name="Booking available-slots of scheduled service",
    )

    if is_ok(response):
        check(
            "available-slots follows the schedule",
            slot_pairs(response.json()) == expected_slots
            and response.json().get("duration") == 45,
            response.json(),
        )

    # --------------------------------------------------------
    # BOOKING AGAINST THE SCHEDULE
    # --------------------------------------------------------

    base = {
        "business_id": BUSINESS_ID,
        "service_id": SCHEDULED_SERVICE_ID,
        "branch_id": BRANCH_ID,
        "booking_date": day.isoformat(),
        "guest_count": 1,
    }

    response = request(
        "POST",
        "/bookings/create",
        headers=CUSTOMER_HEADERS,
        json={**base, "start_time": "10:30", "end_time": "11:15"},
        expected=(200,),
        name="Book scheduled slot 10:30",
    )

    scheduled_booking_id = get_id(response)

    if is_ok(response):
        check_order(
            "Scheduled booking",
            response.json(),
            {("service", SCHEDULED_SERVICE_ID): ("BRON Scheduled Service", 120000.0, 1)},
            120000.0,
        )

    response = availability(day, "Availability after booking 10:30")

    if is_ok(response):
        by_start = {slot.get("start_time"): slot for slot in response.json().get("slots") or []}
        check(
            "10:30 is full, other slots free",
            by_start.get("10:30", {}).get("available_spots") == 0
            and by_start.get("10:30", {}).get("is_available") is False
            and by_start.get("07:00", {}).get("available_spots") == 1,
            response.json().get("slots"),
        )

    response = available_dates("Available dates after booking")

    if is_ok(response):
        check(
            "Scheduled date now has 2 free slots",
            response.json() == [{"date": day.isoformat(), "free_slots": 2}],
            response.json(),
        )

    for target, start, end, message, label in (
        (day, "12:00", "12:45", "Selected time is not in the service schedule", "Unscheduled time"),
        (day, "07:00", "07:30", "end_time must be 07:45 for the 07:00 slot", "Wrong slot length"),
        (day_off, "07:00", "07:45", "Service is not available on this date", "Day off"),
        (unlisted, "07:00", "07:45", "Service is not available on this date", "Date not in schedule"),
        (blocked, "10:00", "10:45", "Selected date is blocked", "Blocked date"),
    ):
        response = request(
            "POST",
            "/bookings/create",
            headers=CUSTOMER_HEADERS,
            json={**base, "booking_date": target.isoformat(), "start_time": start, "end_time": end},
            expected=(400,),
            name=f"Book scheduled service: {label} -> 400",
        )

        check_detail(f"{label} message", response, message)

    # --------------------------------------------------------
    # RESCHEDULE AGAINST THE SCHEDULE
    # --------------------------------------------------------

    if scheduled_booking_id:

        response = request(
            "PATCH",
            f"/bookings/{scheduled_booking_id}/reschedule",
            headers=CUSTOMER_HEADERS,
            json={"booking_date": day.isoformat(), "start_time": "07:00", "end_time": "07:45"},
            expected=(200,),
            name="Reschedule to 07:00 (before working hours)",
        )

        if is_ok(response):
            check(
                "Rescheduled to the 07:00 slot",
                response.json().get("start_time") == "07:00:00"
                and response.json().get("end_time") == "07:45:00",
                response.json(),
            )

        for target, start, end, message, label in (
            (day, "12:00", "12:45", "Selected time is not in the service schedule", "unscheduled time"),
            (day, "22:30", "23:00", "end_time must be 23:15 for the 22:30 slot", "wrong slot length"),
            (day_off, "07:00", "07:45", "Service is not available on this date", "day off"),
        ):
            response = request(
                "PATCH",
                f"/bookings/{scheduled_booking_id}/reschedule",
                headers=CUSTOMER_HEADERS,
                json={"booking_date": target.isoformat(), "start_time": start, "end_time": end},
                expected=(400,),
                name=f"Reschedule to {label} -> 400",
            )

            check_detail(f"Reschedule {label} message", response, message)

    # --------------------------------------------------------
    # UPDATE THE SCHEDULE
    # --------------------------------------------------------

    def update(payload, name, expected=(200,)):
        return request(
            "PUT",
            service_endpoint,
            headers=OWNER_HEADERS,
            json=payload,
            expected=expected,
            name=name,
        )

    response = update({"price": "125000.00"}, "PUT without availability")

    if is_ok(response):
        check(
            "Missing availability keeps the schedule",
            response.json().get("availability") == expected_schedule,
            response.json().get("availability"),
        )

    response = update({"duration": 90}, "Longer duration breaking 22:30 slot -> 400", expected=(400,))

    check_detail(
        "Duration change message",
        response,
        f"Slot at 22:30 on {day.isoformat()} would end after 23:59",
    )

    response = raw("GET", service_endpoint)

    check(
        "Rejected duration change was not saved",
        get_json(response).get("duration") == 45,
        get_json(response).get("duration"),
    )

    response = update(
        {"availability": [{"date": day.isoformat(), "times": ["09:00", "08:00", "09:00"]}]},
        "PUT replaces the schedule",
    )

    if is_ok(response):
        check(
            "New schedule replaces the old one",
            response.json().get("availability") == [
                {"date": day.isoformat(), "times": ["08:00", "09:00"]}
            ],
            response.json().get("availability"),
        )

    update(
        {"availability": [{"date": day.isoformat(), "times": ["25:00"]}]},
        "PUT with bad time -> 422",
        expected=(422,),
    )

    response = update({"availability": None}, "PUT availability null clears it")

    if is_ok(response):
        check(
            "null clears the schedule",
            response.json().get("availability") == [],
            response.json().get("availability"),
        )

    update(
        {"availability": [{"date": day.isoformat(), "times": ["08:00"]}]},
        "PUT sets a schedule again",
    )

    response = update({"availability": []}, "PUT availability [] clears it")

    if is_ok(response):
        check(
            "[] clears the schedule",
            response.json().get("availability") == [],
            response.json().get("availability"),
        )

    response = availability(day, "Availability after clearing schedule")

    if is_ok(response):
        starts = [slot.get("start_time") for slot in response.json().get("slots") or []]
        check(
            "Back to working hours: slots start at 08:00",
            bool(starts) and starts[0] == "08:00" and "07:00" not in starts,
            starts,
        )

    request(
        "PUT",
        service_endpoint,
        headers=CUSTOMER_HEADERS,
        json={"availability": []},
        expected=(403,),
        name="Customer cannot change the schedule",
    )

    cancel_booking(scheduled_booking_id, "Cancel scheduled booking")


# ============================================================
# STEP 11 — BOOKING PERMISSIONS
# ============================================================

def test_booking_permissions():

    print_section("STEP 11 — BOOKING PERMISSIONS")

    if not BOOKING_ID:

        skip_test(
            "Booking permissions",
            "BOOKING_ID unavailable"
        )

        return

    # CUSTOMER MUST NOT APPROVE

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/approve",
        headers=CUSTOMER_HEADERS,
        expected=(403,),
        name="Customer cannot approve booking",
    )

    # OWNER APPROVES

    response = request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/approve",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Owner approves booking",
    )

    if response is not None and response.status_code == 200:

        data = get_json(response)

        print(
            "    Booking status:",
            data.get("status")
        )


# ============================================================
# STEP 12 — ATTENDANCE
# ============================================================

def test_attendance():

    print_section("STEP 12 — NEW ATTENDANCE FEATURE")

    if not BOOKING_ID:

        skip_test(
            "Attendance",
            "BOOKING_ID unavailable"
        )

        return

    # --------------------------------------------------------
    # CUSTOMER CANNOT CONTROL ATTENDANCE
    # --------------------------------------------------------

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/attendance",
        headers=CUSTOMER_HEADERS,
        json={
            "status": "late",
            "extra_wait_minutes": 10,
        },
        expected=(403,),
        name="Customer cannot change attendance",
    )

    # --------------------------------------------------------
    # INVALID STATUS
    # --------------------------------------------------------

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/attendance",
        headers=OWNER_HEADERS,
        json={
            "status": "something_wrong",
            "extra_wait_minutes": 0,
        },
        expected=(422,),
        name="Reject invalid attendance status",
    )

    # --------------------------------------------------------
    # > 10 MINUTES MUST FAIL
    # --------------------------------------------------------

    request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/attendance",
        headers=OWNER_HEADERS,
        json={
            "status": "late",
            "extra_wait_minutes": 11,
        },
        expected=(400,),
        name="Reject waiting > 10 minutes",
    )

    # --------------------------------------------------------
    # CUSTOMER LATE
    # --------------------------------------------------------

    response = request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/attendance",
        headers=OWNER_HEADERS,
        json={
            "status": "late",
            "extra_wait_minutes": 10,
        },
        expected=(200,),
        name="Customer late + 10 minutes",
    )

    if response is not None and response.status_code == 200:

        data = get_json(response)

        print(
            "    attendance_status:",
            data.get("attendance_status")
        )

        print(
            "    extra_wait_minutes:",
            data.get("extra_wait_minutes")
        )

    # --------------------------------------------------------
    # CUSTOMER VISITED
    # --------------------------------------------------------

    response = request(
        "PATCH",
        f"/bookings/{BOOKING_ID}/attendance",
        headers=OWNER_HEADERS,
        json={
            "status": "visited",
            "extra_wait_minutes": 0,
        },
        expected=(200,),
        name="Mark customer visited",
    )

    if response is not None and response.status_code == 200:

        data = get_json(response)

        print(
            "    status:",
            data.get("status")
        )

        print(
            "    attendance:",
            data.get("attendance_status")
        )


# ============================================================
# STEP 13 — CUSTOMER -> BUSINESS REVIEW
# ============================================================

def test_business_review():

    global BUSINESS_REVIEW_ID

    print_section(
        "STEP 13 — CUSTOMER → BUSINESS REVIEW"
    )

    if not BOOKING_ID:

        skip_test(
            "Business review",
            "BOOKING_ID unavailable"
        )

        return

    payload = {
        "business_id": BUSINESS_ID,
        "booking_id": BOOKING_ID,
        "rating": 5,
        "comment": "Excellent service from BRON test.",
    }

    response = request(
        "POST",
        "/reviews/",
        headers=CUSTOMER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Customer reviews business",
    )

    BUSINESS_REVIEW_ID = get_id(
        response,
        "review_id"
    )

    if BUSINESS_REVIEW_ID:
        print(
            f"    BUSINESS_REVIEW_ID = "
            f"{BUSINESS_REVIEW_ID}"
        )

    request(
        "GET",
        f"/reviews/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business review list",
    )

    # Duplicate should fail

    request(
        "POST",
        "/reviews/",
        headers=CUSTOMER_HEADERS,
        json=payload,
        expected=(400,),
        name="Prevent duplicate business review",
    )


# ============================================================
# STEP 14 — BUSINESS -> CUSTOMER REVIEW
# ============================================================

def test_customer_review():

    global CUSTOMER_REVIEW_ID

    print_section(
        "STEP 14 — BUSINESS → CUSTOMER REVIEW"
    )

    if not BOOKING_ID or not CUSTOMER_ID:

        skip_test(
            "Customer review",
            "BOOKING_ID/CUSTOMER_ID unavailable"
        )

        return

    # --------------------------------------------------------
    # INVALID RATING
    # --------------------------------------------------------

    request(
        "POST",
        f"/reviews/customer/{CUSTOMER_ID}",
        headers=OWNER_HEADERS,
        json={
            "booking_id": BOOKING_ID,
            "rating": 6,
            "comment": "Invalid rating",
        },
        expected=(400,),
        name="Reject customer rating > 5",
    )

    # --------------------------------------------------------
    # VALID REVIEW
    # --------------------------------------------------------

    payload = {
        "booking_id": BOOKING_ID,
        "rating": 5,
        "comment": (
            "Customer arrived and behaved professionally."
        ),
    }

    response = request(
        "POST",
        f"/reviews/customer/{CUSTOMER_ID}",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(200, 201),
        name="Business reviews customer",
    )

    CUSTOMER_REVIEW_ID = get_id(
        response,
        "review_id"
    )

    if CUSTOMER_REVIEW_ID:
        print(
            f"    CUSTOMER_REVIEW_ID = "
            f"{CUSTOMER_REVIEW_ID}"
        )

    # --------------------------------------------------------
    # CUSTOMER REVIEW LIST
    # --------------------------------------------------------

    request(
        "GET",
        f"/reviews/customer/{CUSTOMER_ID}",
        expected=(200,),
        name="Customer review list",
    )

    # --------------------------------------------------------
    # CUSTOMER RATING
    # --------------------------------------------------------

    response = request(
        "GET",
        f"/reviews/customer/{CUSTOMER_ID}/rating",
        expected=(200,),
        name="Customer rating",
    )

    if response is not None and response.status_code == 200:

        data = get_json(response)

        print(
            "    Rating:",
            data.get("rating")
        )

        print(
            "    Reviews:",
            data.get("reviews_count")
        )

        # The booking was marked late, then visited: the new mark replaces
        # the old one instead of adding a second score
        check(
            "Booking rating counts only the current mark",
            data.get("booking_rating") == 5.0
            and data.get("evaluated_bookings_count") == 1
            and (data.get("on_time_count"), data.get("late_count"), data.get("no_show_count")) == (1, 0, 0),
            data,
        )

    # --------------------------------------------------------
    # DUPLICATE MUST FAIL
    # --------------------------------------------------------

    request(
        "POST",
        f"/reviews/customer/{CUSTOMER_ID}",
        headers=OWNER_HEADERS,
        json=payload,
        expected=(400,),
        name="Prevent duplicate customer review",
    )


# ============================================================
# STEP 15 — PROFILE RATING
# ============================================================

def test_customer_profile_rating():

    print_section(
        "STEP 15 — CUSTOMER PROFILE RATING"
    )

    response = request(
        "GET",
        "/users/profile",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Customer profile after review",
    )

    if response is not None and response.status_code == 200:

        data = get_json(response)

        print()
        print("    PROFILE RATING")
        print("    --------------")

        print(
            "    rating:",
            data.get("rating")
        )

        print(
            "    reviews_count:",
            data.get("reviews_count")
        )


# ============================================================
# STEP 16 — FAVORITES
# ============================================================

def test_favorites():

    global FAVORITE_ID

    print_section("STEP 16 — FAVORITES")

    if not BUSINESS_ID:

        skip_test(
            "Favorites",
            "BUSINESS_ID unavailable"
        )

        return

    response = request(
        "POST",
        "/favorites/",
        headers=CUSTOMER_HEADERS,
        json={
            "business_id": BUSINESS_ID
        },
        expected=(200, 201),
        name="Add favorite",
    )

    FAVORITE_ID = get_id(
        response,
        "favorite_id"
    )

    if FAVORITE_ID:
        print(
            f"    FAVORITE_ID = {FAVORITE_ID}"
        )

    request(
        "GET",
        "/favorites/",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Favorite list",
    )


# ============================================================
# STEP 17 — GALLERY
# ============================================================

def test_gallery():

    print_section(
        "STEP 17 — BUSINESS GALLERY"
    )

    if not BUSINESS_ID:

        skip_test(
            "Gallery",
            "BUSINESS_ID unavailable"
        )

        return

    upload_endpoint = f"/business-gallery/upload/{BUSINESS_ID}"
    list_endpoint = f"/business-gallery/business/{BUSINESS_ID}"

    def gallery_order(name):
        response = request(
            "GET",
            list_endpoint,
            expected=(200,),
            name=name,
        )
        if not is_ok(response):
            return None
        return [(img.get("id"), img.get("sort_order")) for img in response.json()]

    # --------------------------------------------------------
    # UPLOAD: appended to the end
    # --------------------------------------------------------

    uploaded = []

    for color, fmt in (("red", "PNG"), ("green", "JPEG"), ("blue", "WEBP")):
        response = request(
            "POST",
            upload_endpoint,
            headers=OWNER_HEADERS,
            files=image_upload(color, fmt),
            expected=(200,),
            name=f"Upload gallery image ({fmt})",
        )

        if is_ok(response):
            uploaded.append(response.json())

    if len(uploaded) != 3:
        return

    a, b, c = (img["id"] for img in uploaded)

    check(
        "Uploads get sort_order 0, 1, 2",
        [img.get("sort_order") for img in uploaded] == [0, 1, 2],
        [img.get("sort_order") for img in uploaded],
    )

    check(
        "Gallery URLs are absolute and served",
        all(
            is_absolute_url(img.get("image")) and media_status(img.get("image")) == 200
            for img in uploaded
        ),
        [img.get("image") for img in uploaded],
    )

    order = gallery_order("Gallery list")
    check("List ordered by upload", order == [(a, 0), (b, 1), (c, 2)], order)

    # --------------------------------------------------------
    # PUT: sort_order and/or image (multipart)
    # --------------------------------------------------------

    def update(image_id, name, files, headers=OWNER_HEADERS, expected=(200,)):
        return request(
            "PUT",
            f"/business-gallery/{image_id}",
            headers=headers,
            files=files,
            expected=expected,
            name=name,
        )

    response = update(a, "Move first image to sort_order 5", {"sort_order": (None, "5")})

    if is_ok(response):
        check(
            "sort_order changed, image kept",
            response.json().get("sort_order") == 5
            and response.json().get("image") == uploaded[0].get("image"),
            response.json(),
        )

    order = gallery_order("Gallery list after reorder")
    check("List ordered by sort_order", order == [(b, 1), (c, 2), (a, 5)], order)

    old_url = uploaded[1].get("image")

    response = update(b, "Replace image file (PUT image)", image_upload("yellow", "PNG"))

    if is_ok(response):
        new_url = response.json().get("image")
        check(
            "Image replaced, sort_order kept",
            is_absolute_url(new_url) and new_url != old_url
            and response.json().get("sort_order") == 1,
            response.json(),
        )
        check(
            "New file served, old file deleted",
            media_status(new_url) == 200 and media_status(old_url) == 404,
            (media_status(new_url), media_status(old_url)),
        )

    response = update(
        c,
        "Replace image and sort_order together",
        {**image_upload("purple", "JPEG"), "sort_order": (None, "0")},
    )

    if is_ok(response):
        check(
            "Both fields applied",
            response.json().get("sort_order") == 0
            and response.json().get("image") != uploaded[2].get("image"),
            response.json(),
        )

    order = gallery_order("Gallery list after updates")
    check("Final order c(0), b(1), a(5)", order == [(c, 0), (b, 1), (a, 5)], order)

    response = update(a, "PUT without image and sort_order -> 400", {"note": (None, "x")}, expected=(400,))
    check_detail("Empty update message", response, "Provide image or sort_order")

    update(a, "PUT with negative sort_order -> 422", {"sort_order": (None, "-1")}, expected=(422,))
    update(a, "PUT with non-integer sort_order -> 422", {"sort_order": (None, "abc")}, expected=(422,))

    response = update(
        a,
        "PUT with non-image file -> 400",
        {"image": ("notes.txt", b"not an image", "text/plain")},
        expected=(400,),
    )
    check_detail("Wrong type message", response, "Only JPEG, PNG or WEBP images are allowed")

    update(a, "Customer cannot update gallery image", {"sort_order": (None, "1")},
           headers=CUSTOMER_HEADERS, expected=(403,))
    update(a, "Gallery update without token rejected", {"sort_order": (None, "1")},
           headers=None, expected=(401,))
    update(999999999, "Update unknown gallery image -> 404", {"sort_order": (None, "1")},
           expected=(404,))

    # --------------------------------------------------------
    # NEW UPLOAD GOES AFTER THE MAXIMUM
    # --------------------------------------------------------

    response = request(
        "POST",
        upload_endpoint,
        headers=OWNER_HEADERS,
        files=image_upload("orange", "PNG"),
        expected=(200,),
        name="Upload after reorder",
    )

    if is_ok(response):
        check(
            "New image gets max sort_order + 1 (6)",
            response.json().get("sort_order") == 6,
            response.json(),
        )

    request(
        "POST",
        upload_endpoint,
        headers=CUSTOMER_HEADERS,
        files=image_upload("red", "PNG"),
        expected=(403,),
        name="Customer cannot upload to gallery",
    )

    response = request(
        "POST",
        upload_endpoint,
        headers=OWNER_HEADERS,
        files={"image": ("notes.txt", b"not an image", "text/plain")},
        expected=(400,),
        name="Non-image gallery upload rejected",
    )
    check_detail("Gallery wrong type message", response, "Only JPEG, PNG or WEBP images are allowed")

    # --------------------------------------------------------
    # LIMIT: 20 IMAGES
    # --------------------------------------------------------

    count = len(get_json(raw("GET", list_endpoint)) or [])
    fill_ok = True

    for index in range(count, 20):
        response = raw(
            "POST",
            upload_endpoint,
            headers=OWNER_HEADERS,
            files=image_upload(f"#{index * 10:06x}", "PNG"),
        )
        fill_ok = fill_ok and is_ok(response)

    check(f"Gallery filled up to 20 images (from {count})", fill_ok)

    response = request(
        "POST",
        upload_endpoint,
        headers=OWNER_HEADERS,
        files=image_upload("black", "PNG"),
        expected=(400,),
        name="21st gallery image rejected",
    )
    check_detail("Gallery limit message", response, "Gallery is limited to 20 images")

    # --------------------------------------------------------
    # DELETE
    # --------------------------------------------------------

    request(
        "DELETE",
        f"/business-gallery/{a}",
        headers=CUSTOMER_HEADERS,
        expected=(403,),
        name="Customer cannot delete gallery image",
    )

    a_url = (find_by_id(get_json(raw("GET", list_endpoint)), a) or {}).get("image")

    request(
        "DELETE",
        f"/business-gallery/{a}",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Owner deletes gallery image",
    )

    order = gallery_order("Gallery list after delete")

    if order is not None:
        check(
            "Deleted image gone, others keep sort_order",
            a not in [image_id for image_id, _ in order]
            and order[:2] == [(c, 0), (b, 1)],
            order[:3],
        )

    check("Deleted gallery file is gone", media_status(a_url) == 404, media_status(a_url))

    # Cleanup: the local media folder shouldn't grow with every run
    for image in get_json(raw("GET", list_endpoint)) or []:
        raw("DELETE", f"/business-gallery/{image['id']}", headers=OWNER_HEADERS)

    remaining = get_json(raw("GET", list_endpoint))
    check("Gallery cleaned up", remaining == [], remaining)


# ============================================================
# SUMMARY
# ============================================================

def print_summary():

    total = PASSED + FAILED + SKIPPED

    print("\n")
    print("=" * 90)
    print("BRON API TEST SUMMARY")
    print("=" * 90)

    print(f"Total:   {total}")
    print(f"Passed:  {PASSED}")
    print(f"Failed:  {FAILED}")
    print(f"Skipped: {SKIPPED}")

    print("=" * 90)

    if FAILED > 0:

        print(
            f"❌ {FAILED} TEST(S) FAILED."
        )

    elif SKIPPED > 0:

        print(
            "⚠️ EXECUTED TESTS PASSED, "
            "BUT SOME TESTS WERE SKIPPED."
        )

    else:

        print(
            "🏁 ALL BRON API TESTS PASSED."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 90)
    print("BRON BACKEND API INTEGRATION TEST")
    print("=" * 90)

    print(f"Target: {BASE_URL}")
    print(f"Run ID: {RUN_ID}")

    # --------------------------------------------------------
    # SERVER
    # --------------------------------------------------------

    if not test_server():

        print()
        print("❌ API server is unavailable.")
        print()
        print("Start Django first:")
        print()
        print(
            "    python3 manage.py runserver 8001"
        )
        print()

        sys.exit(1)

    # --------------------------------------------------------
    # AUTH
    # --------------------------------------------------------

    if not test_authentication():

        print()
        print(
            "❌ Authentication setup failed."
        )
        print(
            "Cannot continue safely."
        )

        print_summary()

        sys.exit(1)

    # --------------------------------------------------------
    # REST OF API
    # --------------------------------------------------------

    test_user_profile()
    test_notification_settings()
    test_categories()

    business_ok = test_business()

    test_business_application()

    if business_ok:

        test_branch()
        test_services()
        test_products()
        test_product_image()
        test_staff()

        test_working_hours()
        test_blocked_dates()

        booking_ok = test_booking()

        test_service_schedule()

        if booking_ok:

            test_booking_permissions()
            test_attendance()

            test_business_review()
            test_customer_review()
            test_customer_profile_rating()

        else:

            skip_test(
                "Booking permission tests",
                "Booking creation failed"
            )

            skip_test(
                "Attendance tests",
                "Booking creation failed"
            )

            skip_test(
                "Review tests",
                "Booking creation failed"
            )

        test_favorites()
        test_gallery()

    else:

        skip_test(
            "Remaining business tests",
            "Business creation failed"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_summary()

    if FAILED > 0:
        sys.exit(1)

    if SKIPPED > 0:
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()