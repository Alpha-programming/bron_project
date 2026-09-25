import os
import requests
import sys
import uuid
from datetime import date, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

# LOCAL
BASE_URL = os.getenv("BRON_API_URL", "http://127.0.0.1:8001/api")

# PRODUCTION — use later:
# BASE_URL = "https://api.bronofficial.com/api"

TIMEOUT = 15
RUN_ID = uuid.uuid4().hex[:8]


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

WORKING_HOURS_ID = None
BLOCKED_DATE_ID = None

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
    expected=(200,),
    name=None,
):
    global PASSED, FAILED

    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
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

    request(
        "GET",
        f"/businesses/{BUSINESS_ID}",
        expected=(200,),
        name="Business detail",
    )

    request(
        "GET",
        "/businesses/search",
        params={"q": "BRON"},
        expected=(200,),
        name="Business search",
    )

    request(
        "GET",
        "/businesses/category/gym",
        expected=(200,),
        name="Business category",
    )

    request(
        "GET",
        f"/businesses/{BUSINESS_ID}/stats",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Business stats",
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

        request(
            "GET",
            f"/services/{SERVICE_ID}",
            expected=(200,),
            name="Service detail",
        )

    else:
        print_response_body(response)

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

    blocked_date = (
        date.today()
        + timedelta(days=30)
    )

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

    request(
        "GET",
        "/blocked-dates/check",
        params={
            "business_id": BUSINESS_ID,
            "target_date": blocked_date.isoformat(),
        },
        expected=(200,),
        name="Check blocked date",
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
            f"from core.models import Business; Business.objects.filter(id={BUSINESS_ID}).update(is_active=True)",
        ],
        capture_output=True,
    )

    return result.returncode == 0


def test_booking():

    global BOOKING_ID

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

    if not activate_business_locally():

        skip_test(
            "Booking tests",
            "Business must be approved in admin (is_active=True) before booking"
        )

        return False

    booking_date = (
        date.today()
        + timedelta(days=7)
    )

    payload = {
        "business_id": BUSINESS_ID,
        "service_id": SERVICE_ID,
        "branch_id": BRANCH_ID,
        "staff_id": STAFF_ID,
        "booking_date": booking_date.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "guest_count": 1,
        "product_ids": (
            [PRODUCT_ID]
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
        name="Customer creates booking",
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

    request(
        "GET",
        "/bookings/my",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Customer booking list",
    )

    request(
        "GET",
        f"/bookings/{BOOKING_ID}",
        headers=CUSTOMER_HEADERS,
        expected=(200,),
        name="Booking detail",
    )

    request(
        "GET",
        f"/bookings/business/{BUSINESS_ID}",
        headers=OWNER_HEADERS,
        expected=(200,),
        name="Business bookings",
    )

    if STAFF_ID:

        request(
            "GET",
            f"/bookings/staff/{STAFF_ID}",
            headers=OWNER_HEADERS,
            expected=(200,),
            name="Staff booking list",
        )

        request(
            "GET",
            "/bookings/available-slots",
            params={
                "business_id": BUSINESS_ID,
                "staff_id": STAFF_ID,
                "target_date": booking_date.isoformat(),
            },
            expected=(200,),
            name="Available booking slots",
        )

    return True


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
        expected=(400,),
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

def test_gallery_reads():

    print_section(
        "STEP 17 — BUSINESS GALLERY"
    )

    if not BUSINESS_ID:

        skip_test(
            "Gallery",
            "BUSINESS_ID unavailable"
        )

        return

    request(
        "GET",
        f"/business-gallery/business/{BUSINESS_ID}",
        expected=(200,),
        name="Business gallery",
    )


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

    business_ok = test_business()

    if business_ok:

        test_branch()
        test_services()
        test_products()
        test_staff()

        test_working_hours()
        test_blocked_dates()

        booking_ok = test_booking()

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
        test_gallery_reads()

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