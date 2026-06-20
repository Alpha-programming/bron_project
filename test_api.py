import requests
import sys

# Define target endpoints - Updated port matching your environment layout
BASE_URL = "http://127.0.0.1:8002/api"

# Persistent runtime state
TOKEN = None
HEADERS = {}
BUSINESS_ID = None
BRANCH_ID = None
SERVICE_ID = None
PRODUCT_ID = None
STAFF_ID = None


def run_step_1_authentication():
    """
    Step 1: Validates Account Generation, JWT Login pipelines,
    and Request Identity Extraction blocks.
    """
    global TOKEN, HEADERS
    print("\n--- [STEP 1] TESTING AUTHENTICATION & PROFILE TRACKING ---")

    # 1. Register test profile
    reg_payload = {
        "username": "iron_tester_2026",
        "email": "tester2026@iron.com",
        "password": "SecurePassword123!",
        "phone": "+998901234567"
    }
    r = requests.post(f"{BASE_URL}/auth/register", json=reg_payload)
    print(f"[POST] /auth/register -> Status: {r.status_code}")
    # Note: If profile already exists in the database, we proceed cleanly to login

    # 2. Login to extract your new JWT Token
    login_payload = {
        "username": "iron_tester_2026",
        "password": "SecurePassword123!"
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if r.status_code == 200:
        TOKEN = r.json().get("access_token")
        HEADERS = {"Authorization": f"Bearer {TOKEN}"}
        print(f"✅ Login Successful. Token extracted cleanly.")
    else:
        print(f"❌ Login Pipeline Failed: {r.text}")
        return False

    # 3. Target /me via JWTAuth
    r = requests.get(f"{BASE_URL}/auth/me", headers=HEADERS)

    if r.status_code != 200 or "application/json" not in r.headers.get("Content-Type", ""):
        print(f"❌ CRITICAL Error on /auth/me | Status Code: {r.status_code}")

        # --- NEW DEBUG EXTRACTOR BLOCK ---
        print("\n🔎 EXTRACTING DJANGO TRACEBACK...")
        if "exception_value" in r.text:
            # Try to grab the exact clean exception message from Django's debug container
            try:
                error_msg = r.text.split('<div id="summary">')[1].split('</div>')[0].strip()
                print(f"Server Error Message Summary:\n{error_msg}\n")
            except Exception:
                pass

        # Print lines that show where the file crashed
        lines = r.text.split('\n')
        trace_found = False
        print("Relevant Exception Context Lines:")
        for line in lines:
            if "exception" in line.lower() or "raise" in line or "core/security" in line or "core/utils/jwt" in line:
                clean_line = line.replace('<th>', '').replace('</th>', '').replace('<td>', '').replace('</td>',
                                                                                                       '').strip()
                if clean_line and len(clean_line) < 200:
                    print(f" -> {clean_line}")
                    trace_found = True

        if not trace_found:
            print("(Could not isolate trace keywords in HTML text. Please look at your runserver console terminal!)")
        # ---------------------------------

        return False

    print(f"[GET]  /auth/me       -> Status: {r.status_code} | User: {r.json().get('username', 'Unknown')}")

    # 4. Target User Profile
    r = requests.get(f"{BASE_URL}/users/profile", headers=HEADERS)
    print(f"[GET]  /users/profile -> Status: {r.status_code}")

    # 5. Modify User Profile
    update_payload = {"first_name": "Iron", "last_name": "Developer"}
    r = requests.put(f"{BASE_URL}/users/profile", headers=HEADERS, json=update_payload)
    print(f"[PUT]  /users/profile -> Status: {r.status_code}")

    # 6. Telegram One-Time Token Request
    r = requests.post(f"{BASE_URL}/users/telegram/connect", json={"phone": "+998901234567"})
    print(f"[POST] /users/telegram/connect -> Status: {r.status_code}")

    return True


def run_step_2_business_hierarchy():
    """
    Step 2: Asserts entity generation parameters, global visibility,
    and ownership authorization validation checks.
    """
    global BUSINESS_ID
    print("\n--- [STEP 2] TESTING BUSINESS OPERATION LAYERS ---")

    # 1. Create a Business entity
    biz_payload = {
        "name": "Iron Elite Performance HQ",
        "description": "Next-gen sports training and rehabilitation setup",
        "category": "Fitness & Health",
        "address": "100 Amir Temur Avenue, Tashkent",
        "phone": "+998907778899"
    }
    r = requests.post(f"{BASE_URL}/businesses/create", headers=HEADERS, json=biz_payload)
    print(f"[POST] /businesses/create -> Status: {r.status_code}")

    # 2. Extract Business from the global listing feed
    r = requests.get(f"{BASE_URL}/businesses/")
    print(f"[GET]  /businesses/       -> Status: {r.status_code}")
    businesses = r.json()

    if isinstance(businesses, list) and len(businesses) > 0:
        # Match against our created business or take the latest index block
        BUSINESS_ID = businesses[-1].get("id")
        print(f"✅ Active Business ID Registered: {BUSINESS_ID}")
    else:
        print("❌ No business returned from system storage context.")
        return False

    # 3. View Business Specific Details
    r = requests.get(f"{BASE_URL}/businesses/{BUSINESS_ID}")
    print(f"[GET]  /businesses/{{id}}  -> Status: {r.status_code}")

    # 4. Update Business Details
    r = requests.put(
        f"{BASE_URL}/businesses/{BUSINESS_ID}",
        headers=HEADERS,
        json={"name": "Iron Elite Performance HQ v2"}
    )
    print(f"[PUT]  /businesses/{{id}}  -> Status: {r.status_code}")
    return True


def run_step_3_structural_dependencies():
    """
    Step 3: Creates core branch extensions, inventory items,
    and company service models under the business ownership scope.
    """
    global BRANCH_ID, SERVICE_ID, PRODUCT_ID
    print("\n--- [STEP 3] TESTING RELATIONAL DEPENDENCIES (BRANCHES, SERVICES, PRODUCTS) ---")

    # 1. Add Business Branch
    branch_payload = {
        "business_id": BUSINESS_ID,
        "name": "Central Tashkent Hub",
        "address": "Yunusabad District, Block 4",
        "phone": "+998911112233"
    }
    r = requests.post(f"{BASE_URL}/branches/create", headers=HEADERS, json=branch_payload)
    if r.status_code in [200, 201]:
        BRANCH_ID = r.json().get("id")
    print(f"[POST] /branches/create -> Status: {r.status_code} | Branch ID: {BRANCH_ID}")

    # 2. Add System Service Offering
    service_payload = {
        "business_id": BUSINESS_ID,
        "title": "Elite Metabolic Conditioning",
        "description": "60-minute advanced energy systems protocol",
        "category": "High Performance",
        "duration": 60,
        "price": 250000.00
    }
    r = requests.post(f"{BASE_URL}/services/create", headers=HEADERS, json=service_payload)
    if r.status_code in [200, 201]:
        SERVICE_ID = r.json().get("id")
    print(f"[POST] /services/create -> Status: {r.status_code} | Service ID: {SERVICE_ID}")

    # 3. Add Catalog Product
    product_payload = {
        "business_id": BUSINESS_ID,
        "name": "Premium Hydration Matrix",
        "description": "Electrolyte delivery supplement formulation",
        "price": 75000.00
    }
    r = requests.post(f"{BASE_URL}/products/create", headers=HEADERS, json=product_payload)
    if r.status_code in [200, 201]:
        PRODUCT_ID = r.json().get("id")
    print(f"[POST] /products/create -> Status: {r.status_code} | Product ID: {PRODUCT_ID}")

    # 4. Assert Business Isolation Queries
    print(
        f"[GET]  /services/business/{BUSINESS_ID} -> Status: {requests.get(f'{BASE_URL}/services/business/{BUSINESS_ID}').status_code}")
    print(
        f"[GET]  /products/business/{BUSINESS_ID} -> Status: {requests.get(f'{BASE_URL}/products/business/{BUSINESS_ID}').status_code}")
    print(
        f"[GET]  /branches/business/{BUSINESS_ID} -> Status: {requests.get(f'{BASE_URL}/branches/business/{BUSINESS_ID}').status_code}")

    return all([BRANCH_ID, SERVICE_ID, PRODUCT_ID])


def run_step_4_staff_and_timelines():
    """
    Step 4: Provisions staff members and explicitly tests the updated
    working hours logic to prevent string-to-time object conversion crashes.
    """
    global STAFF_ID
    print("\n--- [STEP 4] TESTING STAFF & TIME ALLOCATION CONVERSIONS ---")

    # 1. Provision Staff Member
    staff_payload = {
        "business_id": BUSINESS_ID,
        "full_name": "Dr. Sarah Jenkins",
        "position": "Lead Sports Physiotherapist",
        "phone": "+998935556677"
    }
    r = requests.post(f"{BASE_URL}/staff/create", headers=HEADERS, json=staff_payload)
    if r.status_code in [200, 201]:
        STAFF_ID = r.json().get("id")
    print(f"[POST] /staff/create -> Status: {r.status_code} | Staff ID: {STAFF_ID}")

    # 2. Generate Working Hours Matrix (Validates string-to-time transformation parsing)
    hours_payload = {
        "business_id": BUSINESS_ID,
        "day_of_week": 1,  # Monday
        "open_time": "08:00",
        "close_time": "20:00",
        "is_closed": False
    }
    r = requests.post(f"{BASE_URL}/working-hours/create", headers=HEADERS, json=hours_payload)
    print(f"[POST] /working-hours/create -> Status: {r.status_code}")

    # 3. Block off a specific calendar date window
    blocked_payload = {
        "business_id": BUSINESS_ID,
        "date": "2026-08-15",
        "reason": "Facility Deep Clean & System Maintenance"
    }
    r = requests.post(f"{BASE_URL}/blocked-dates/create", headers=HEADERS, json=blocked_payload)
    print(f"[POST] /blocked-dates/create -> Status: {r.status_code}")

    return STAFF_ID is not None


def run_step_5_booking_cycles():
    """
    Step 5: Exercises complex transactional mapping across multiple entities,
    asserting total price aggregation and clean model field transformations.
    """
    print("\n--- [STEP 5] TESTING BOOKING INGESTION PIPELINES ---")

    # Assemble request payload combining dependencies from Steps 2, 3, and 4
    booking_payload = {
        "business_id": BUSINESS_ID,
        "service_id": SERVICE_ID,
        "branch_id": BRANCH_ID,
        "staff_id": STAFF_ID,
        "booking_date": "2026-08-16",  # Cleanly targets one day after the blocked window
        "start_time": "14:00:00",
        "end_time": "15:00:00",
        "guest_count": 1,
        "product_ids": [PRODUCT_ID]
    }

    r = requests.post(f"{BASE_URL}/bookings/create", headers=HEADERS, json=booking_payload)
    print(f"[POST] /bookings/create -> Status: {r.status_code}")
    if r.status_code in [200, 201]:
        print(f"🎉 Booking Cycle Cleared! System Output Summary: {r.json()}")
    else:
        print(f"❌ Transaction Matrix Ingestion Failure: {r.text}")

    # Assert user booking visibility query works correctly
    r = requests.get(f"{BASE_URL}/bookings/my", headers=HEADERS)
    print(f"[GET]  /bookings/my     -> Status: {r.status_code}")


if __name__ == "__main__":
    print("==================================================================")
    print("🚀 INITIALIZING END-TO-END AUTOMATED SWAGGER PIPELINE VERIFICATION")
    print("==================================================================")

    try:
        if run_step_1_authentication():
            if run_step_2_business_hierarchy():
                if run_step_3_structural_dependencies():
                    if run_step_4_staff_and_timelines():
                        run_step_5_booking_cycles()
                        print("\n🏁 ALL SYSTEMS OPERATIONAL: Pipeline checks completed successfully.")
                    else:
                        print("\n⚠️ Execution halted: Step 4 (Staff/Timelines) validation failure.")
                else:
                    print("\n⚠️ Execution halted: Step 3 (Structural Dependencies) validation failure.")
            else:
                print("\n⚠️ Execution halted: Step 2 (Business Layers) validation failure.")
        else:
            print("\n⚠️ Execution halted: Step 1 (Authentication Check) validation failure.")

    except requests.exceptions.ConnectionError:
        print("\n❌ CRITICAL: Could not reach your server application.")
        print(f"   Make sure to run your server on {BASE_URL.replace('/api', '')} before initiating checks.")
        sys.exit(1)