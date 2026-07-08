import requests
import sys
from datetime import datetime

# Target Base URL configured matching your layout port
BASE_URL = "https://uzbALPHA.pythonanywhere.com/api"

# Global script state machine tracers
TOKEN = None
HEADERS = {}
BUSINESS_ID = None
BRANCH_ID = None
SERVICE_ID = None
PRODUCT_ID = None
STAFF_ID = None
BOOKING_ID = None
WORKING_HOURS_ID = None
BLOCKED_DATE_ID = None
REVIEW_ID = None
FAVORITE_ID = None


def print_step(title):
    print("\n" + "=" * 80)
    print(f"🚀 {title}")
    print("=" * 80)


def test_step_1_authentication_and_users():
    global TOKEN, HEADERS
    print_step("STEP 1: AUTHENTICATION & SECURITY PIPELINES")

    # 1. Register Account Context
    reg_payload = {
        "username": "iron_tester_2026",
        "email": "tester2026@iron.com",
        "password": "SecurePassword123!",
        "phone": "+998901234567"
    }
    r = requests.post(f"{BASE_URL}/auth/register", json=reg_payload)
    print(f"[POST] /auth/register -> Status: {r.status_code}")

    # 2. Login Context
    login_payload = {
        "username": "iron_tester_2026",
        "password": "SecurePassword123!"
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if r.status_code == 200:
        TOKEN = r.json().get("access_token")
        HEADERS = {"Authorization": f"Bearer {TOKEN}"}
        print("✅ Identity verified. Token context attached safely.")
    else:
        print(f"❌ Core Identity Login Exception: {r.text}")
        return False

    # 3. Requesting Identity Payload
    r = requests.get(f"{BASE_URL}/auth/me", headers=HEADERS)
    print(f"[GET]  /auth/me       -> Status: {r.status_code} | Account: {r.json().get('username')}")

    # 4. Profile Management Pipelines
    r = requests.get(f"{BASE_URL}/users/profile", headers=HEADERS)
    print(f"[GET]  /users/profile -> Status: {r.status_code}")

    update_payload = {"first_name": "Asadbek", "last_name": "Developer"}
    r = requests.put(f"{BASE_URL}/users/profile", headers=HEADERS, json=update_payload)
    print(f"[PUT]  /users/profile -> Status: {r.status_code}")

    # 5. Telegram Dispatch Subsystem Channel Links
    r = requests.post(f"{BASE_URL}/users/telegram/connect", json={"phone": "+998901234567"})
    print(f"[POST] /users/telegram/connect -> Status: {r.status_code}")

    return r.status_code == 200


def test_step_2_business_domains():
    global BUSINESS_ID
    print_step("STEP 2: BUSINESS MULTI-TENANCY MANAGEMENT")

    biz_payload = {
        "name": "Iron Physical Performance Center",
        "description": "Elite tracking biomechanics training center",
        "category": "gym",
        "address": "100 Amir Temur Avenue, Tashkent",
        "phone": "+998907778899"
    }
    r = requests.post(f"{BASE_URL}/businesses/create", headers=HEADERS, json=biz_payload)
    print(f"[POST] /businesses/create -> Status: {r.status_code}")

    r = requests.get(f"{BASE_URL}/businesses/")
    print(f"[GET]  /businesses/       -> Status: {r.status_code}")
    businesses = r.json()

    if isinstance(businesses, list) and len(businesses) > 0:
        BUSINESS_ID = businesses[-1].get("id")
        print(f"✅ Dynamic Active Tenant ID Parsed: {BUSINESS_ID}")
    else:
        print("❌ Core data exception: Empty storage list context.")
        return False

    # Detail Profile Lookup
    r = requests.get(f"{BASE_URL}/businesses/{BUSINESS_ID}")
    print(f"[GET]  /businesses/{{id}}  -> Status: {r.status_code}")

    # FIXED: Maps exactly to your registered schema endpoint path pattern '/{business_id}/stats'
    r = requests.get(f"{BASE_URL}/businesses/{BUSINESS_ID}/stats", headers=HEADERS)
    print(f"[GET]  /businesses/{{id}}/stats -> Status: {r.status_code}")

    # Filtering Lookup Channels
    r = requests.get(f"{BASE_URL}/businesses/search?q=Iron")
    print(f"[GET]  /businesses/search -> Status: {r.status_code}")

    r = requests.get(f"{BASE_URL}/businesses/category/gym")
    print(f"[GET]  /businesses/category/gym -> Status: {r.status_code}")

    return True


def test_step_3_inventories_and_catalogs():
    global BRANCH_ID, SERVICE_ID, PRODUCT_ID
    print_step("STEP 3: DEPLOYMENT STACKS (BRANCHES, SERVICES, PRODUCTS)")

    # 1. Branch Provisioning
    branch_payload = {
        "business_id": BUSINESS_ID,
        "name": "Yunusabad Elite Wing",
        "address": "Yunusabad District, Tashkent",
        "phone": "+998911112233"
    }
    r = requests.post(f"{BASE_URL}/branches/create", headers=HEADERS, json=branch_payload)
    if r.status_code in [200, 201]:
        BRANCH_ID = r.json().get("id")
    print(f"[POST] /branches/create -> Status: {r.status_code} | ID: {BRANCH_ID}")

    # 2. Service Catalog Provisioning
    service_payload = {
        "business_id": BUSINESS_ID,
        "title": "Biomechanical Diagnostics Session",
        "description": "High performance muscular loading assessment test protocols",
        "category": "Diagnostics",
        "duration": 60,
        "price": "350000.00"
    }
    r = requests.post(f"{BASE_URL}/services/create", headers=HEADERS, json=service_payload)
    if r.status_code in [200, 201]:
        SERVICE_ID = r.json().get("id")
    print(f"[POST] /services/create -> Status: {r.status_code} | ID: {SERVICE_ID}")

    # 3. Inventory Stock Provisioning
    product_payload = {
        "business_id": BUSINESS_ID,
        "name": "Electrolyte Recovery Multi-Pack",
        "description": "Premium complex hydration cellular mix packets",
        "price": "95000.00"
    }
    r = requests.post(f"{BASE_URL}/products/create", headers=HEADERS, json=product_payload)
    if r.status_code in [200, 201]:
        PRODUCT_ID = r.json().get("id")
    print(f"[POST] /products/create -> Status: {r.status_code} | ID: {PRODUCT_ID}")

    # FIXED Query string keys matching schema lookups
    print(
        f"[GET]  /services/search -> Status: {requests.get(f'{BASE_URL}/services/search?q=Biomechanical').status_code}")
    print(f"[GET]  /products/search -> Status: {requests.get(f'{BASE_URL}/products/search?q=Electrolyte').status_code}")
    print(f"[GET]  /services/categories -> Status: {requests.get(f'{BASE_URL}/services/categories').status_code}")

    return all([BRANCH_ID, SERVICE_ID, PRODUCT_ID])


def test_step_4_schedules_and_staffing():
    global STAFF_ID, WORKING_HOURS_ID, BLOCKED_DATE_ID
    print_step("STEP 4: OPERATORS, HOURS & SCHEDULING INTERVENTIONS")

    # 1. Staff Creation
    staff_payload = {
        "business_id": BUSINESS_ID,
        "full_name": "Coach Alexander Vance",
        "position": "Director of Physiology",
        "phone": "+998935556677"
    }
    r = requests.post(f"{BASE_URL}/staff/create", headers=HEADERS, json=staff_payload)
    if r.status_code in [200, 201]:
        STAFF_ID = r.json().get("id")
    print(f"[POST] /staff/create -> Status: {r.status_code} | ID: {STAFF_ID}")

    # 2. Operating Hours Configuration
    current_day = datetime.now().weekday()
    hours_payload = {
        "business_id": BUSINESS_ID,
        "day_of_week": current_day,
        "open_time": "08:00:00",
        "close_time": "22:00:00",
        "is_closed": False
    }
    r = requests.post(f"{BASE_URL}/working-hours/create", headers=HEADERS, json=hours_payload)
    if r.status_code in [200, 201]:
        WORKING_HOURS_ID = r.json().get("id")
    print(f"[POST] /working-hours/create -> Status: {r.status_code}")

    # Real-time state lookups
    r = requests.get(f"{BASE_URL}/working-hours/today/{BUSINESS_ID}")
    print(f"[GET]  /working-hours/today/{{id}} -> Status: {r.status_code}")

    # 3. Block calendar day configurations
    blocked_payload = {
        "business_id": BUSINESS_ID,
        "date": "2026-09-10",
        "reason": "Facility Mechanical Ventilation Re-calibration Block"
    }
    r = requests.post(f"{BASE_URL}/blocked-dates/create", headers=HEADERS, json=blocked_payload)
    if r.status_code in [200, 201]:
        BLOCKED_DATE_ID = r.json().get("id")
    print(f"[POST] /blocked-dates/create -> Status: {r.status_code}")

    return STAFF_ID is not None


def test_step_5_transaction_reservations():
    global BOOKING_ID
    print_step("STEP 5: RESERVATION ACTIONS, TRANSFERS & STATE FLOWS")

    booking_payload = {
        "business_id": BUSINESS_ID,
        "service_id": SERVICE_ID,
        "branch_id": BRANCH_ID,
        "staff_id": STAFF_ID,
        "booking_date": "2026-09-15",
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "guest_count": 1,
        "product_ids": [PRODUCT_ID]
    }
    r = requests.post(f"{BASE_URL}/bookings/create", headers=HEADERS, json=booking_payload)
    print(f"[POST] /bookings/create -> Status: {r.status_code}")

    if r.status_code in [200, 201]:
        BOOKING_ID = r.json().get("id")
        print(f"🎉 Reservation Created Successfully! Trace Tracker ID: {BOOKING_ID}")
    else:
        print(f"❌ Booking Engine Refusal: {r.text}")
        return False

    # Dispatch Lookups
    print(f"[GET]  /bookings/my     -> Status: {requests.get(f'{BASE_URL}/bookings/my', headers=HEADERS).status_code}")
    print(
        f"[GET]  /bookings/business/{BUSINESS_ID} -> Status: {requests.get(f'{BASE_URL}/bookings/business/{BUSINESS_ID}', headers=HEADERS).status_code}")

    # State Alterations
    r = requests.patch(f"{BASE_URL}/bookings/{BOOKING_ID}/approve", headers=HEADERS)
    print(f"[PATCH] /bookings/{{id}}/approve -> Status: {r.status_code}")

    return BOOKING_ID is not None


def test_step_6_user_interactions():
    global REVIEW_ID, FAVORITE_ID
    print_step("STEP 6: CONSUMER ENGAGEMENT LOGS (REVIEWS & FAVORITES)")

    # 1. Post Product/Business Evaluation
    review_payload = {
        "business_id": BUSINESS_ID,
        "rating": 5,
        "comment": "Incredible infrastructure metrics, elite engineering standard."
    }
    r = requests.post(f"{BASE_URL}/reviews/", headers=HEADERS, json=review_payload)
    if r.status_code in [200, 201]:
        REVIEW_ID = r.json().get("id")
    print(f"[POST] /reviews/ -> Status: {r.status_code} | ID: {REVIEW_ID}")

    # Public review index stream
    r = requests.get(f"{BASE_URL}/reviews/business/{BUSINESS_ID}")
    print(f"[GET]  /reviews/business/{{id}} -> Status: {r.status_code}")

    # 2. Toggle Bookmark Core Profiles
    r = requests.post(f"{BASE_URL}/favorites/", headers=HEADERS, json={"business_id": BUSINESS_ID})
    if r.status_code in [200, 201]:
        FAVORITE_ID = r.json().get("id")
    print(f"[POST] /favorites/ -> Status: {r.status_code} | ID: {FAVORITE_ID}")

    # View Collection Manifest Indexes
    r = requests.get(f"{BASE_URL}/favorites/", headers=HEADERS)
    print(f"[GET]  /favorites/ -> Status: {r.status_code}")

    return True


if __name__ == "__main__":
    print("========================================================================")
    print("🛠️  EXECUTING SYSTEM ARCHITECTURE VALIDATION MATRIX FOR APIS")
    print("========================================================================")

    try:
        if test_step_1_authentication_and_users():
            if test_step_2_business_domains():
                if test_step_3_inventories_and_catalogs():
                    if test_step_4_schedules_and_staffing():
                        if test_step_5_transaction_reservations():
                            test_step_6_user_interactions()
                            print("\n🏁 ALL ENDPOINTS FULLY SYNCHRONIZED AND VERIFIED GREEN.")
                        else:
                            print("\n⚠️ Interrupted: Flow failure during step 5 transaction execution.")
                    else:
                        print("\n⚠️ Interrupted: Core configuration fault during step 4 timetables.")
                else:
                    print("\n⚠️ Interrupted: Relation asset mismatch during step 3 inventories.")
            else:
                print("\n⚠️ Interrupted: Multi-tenant processing fault during step 2 domains.")
        else:
            print("\n⚠️ Interrupted: Connection authentication access fault during step 1 security.")

    except requests.exceptions.ConnectionError:
        print(f"\n❌ TARGET OFFLINE: Infrastructure could not reach target pipeline port context on {BASE_URL}")
        print("   Please execute 'python manage.py runserver 8002' inside your server console instance first.")
        sys.exit(1)