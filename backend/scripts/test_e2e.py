"""
E2E Rate Limit Test Script
Tests the full detection + rate limiting flow via direct API calls.
Verifies that both /detect and /api/detect share the same daily counter.
"""
import httpx
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

BACKEND_URL = "http://localhost:8000"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtZHJubnZtdWdiYnhzamN0Y3p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0MTgxOTgsImV4cCI6MjA5NTk5NDE5OH0.b21jZh9e1Fn6jM7zRIkQYXApCX4-nWiEWb5FIBv-NC8"
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

TEST_EMAIL = "phase5test@proton.me"
TEST_PASSWORD = "Phase5Test!"
TEST_IMAGE = os.path.join(os.path.dirname(__file__), "..", "..", "test_real.jpg")

DAILY_LIMIT = 5


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def login(email, password):
    """Login via Supabase auth and return access token."""
    r = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        },
        json={"email": email, "password": password},
    )
    if r.status_code != 200:
        print(f"  [FAIL] Login failed: {r.status_code} {r.text}")
        return None, None
    data = r.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    print(f"  [OK] Logged in as {email} (user_id={user_id[:8]}...)")
    return token, user_id


def reset_usage(user_id):
    """Reset the user's daily usage counter to 0."""
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    # Delete existing usage row (if any)
    r = httpx.delete(
        f"{SUPABASE_URL}/rest/v1/usage?user_id=eq.{user_id}",
        headers=headers,
    )
    print(f"  [OK] Usage counter reset (status={r.status_code})")


def detect_image(token, scan_number):
    """Call POST /detect with the test image."""
    with open(TEST_IMAGE, "rb") as f:
        r = httpx.post(
            f"{BACKEND_URL}/detect",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test_real.jpg", f, "image/jpeg")},
            timeout=60.0,
        )
    status = r.status_code
    if status == 200:
        data = r.json()
        has_heatmap = bool(data.get("heatmap"))
        print(f"  Scan #{scan_number}: {status} OK | verdict={data['label']} conf={data['confidence']:.1f}% heatmap={'yes' if has_heatmap else 'NO'}")
        return True
    elif status == 429:
        print(f"  Scan #{scan_number}: {status} RATE LIMITED | {r.json().get('detail', '')}")
        return False
    else:
        print(f"  Scan #{scan_number}: {status} ERROR | {r.text[:200]}")
        return None


def generate_api_key(token):
    """Generate an API key via POST /api-keys/generate."""
    r = httpx.post(
        f"{BACKEND_URL}/api-keys/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code == 200:
        data = r.json()
        raw_key = data["raw_key"]
        print(f"  [OK] API key generated: {raw_key[:12]}...")
        return raw_key
    else:
        print(f"  [FAIL] API key generation failed: {r.status_code} {r.text}")
        return None


def api_detect(api_key):
    """Call POST /api/detect with the API key."""
    with open(TEST_IMAGE, "rb") as f:
        r = httpx.post(
            f"{BACKEND_URL}/api/detect",
            headers={"X-API-Key": api_key},
            files={"file": ("test_real.jpg", f, "image/jpeg")},
            timeout=60.0,
        )
    status = r.status_code
    if status == 429:
        print(f"  [OK] /api/detect returned 429: {r.json().get('detail', '')}")
        return 429
    elif status == 200:
        print(f"  [UNEXPECTED] /api/detect returned 200 (should be 429)")
        return 200
    else:
        print(f"  [ERROR] /api/detect returned {status}: {r.text[:200]}")
        return status


def check_dashboard(token):
    """Fetch scan history from Supabase."""
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    # Get the user_id from the token
    r = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {token}",
        },
    )
    user_id = r.json()["id"]

    r2 = httpx.get(
        f"{SUPABASE_URL}/rest/v1/scans",
        headers=headers,
        params={
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": "10",
        },
    )
    scans = r2.json()
    print(f"  [OK] Found {len(scans)} scans in dashboard history")
    for s in scans[:5]:
        print(f"       - {s['filename']} | {s['label']} | {s['confidence']:.1f}%")
    return len(scans)


def main():
    results = {}

    # Step 1: Login
    step("Step 1: Login")
    token, user_id = login(TEST_EMAIL, TEST_PASSWORD)
    if not token:
        print("\n[ABORT] Cannot proceed without login.")
        sys.exit(1)
    results["login"] = "PASS"

    # Step 2: Reset usage counter
    step("Step 2: Reset usage counter")
    reset_usage(user_id)

    # Step 3: Run 5 scans (all should succeed)
    step("Step 3: Run 5 scans via /detect (should all succeed)")
    all_ok = True
    for i in range(1, DAILY_LIMIT + 1):
        ok = detect_image(token, i)
        if ok is not True:
            all_ok = False
            break
        if i < DAILY_LIMIT:
            time.sleep(1)  # Small delay between scans
    results["5_scans"] = "PASS" if all_ok else "FAIL"

    # Step 4: 6th scan should be rate-limited
    step("Step 4: 6th scan via /detect (should return 429)")
    ok = detect_image(token, 6)
    results["rate_limit_ui"] = "PASS" if ok is False else "FAIL"

    # Step 5: Check dashboard
    step("Step 5: Check dashboard scan history")
    scan_count = check_dashboard(token)
    results["dashboard"] = "PASS" if scan_count >= 5 else "FAIL"

    # Step 6: Generate API key
    step("Step 6: Generate API key")
    api_key = generate_api_key(token)
    results["api_key_gen"] = "PASS" if api_key else "FAIL"

    # Step 7: Verify /api/detect also returns 429
    step("Step 7: Verify /api/detect also returns 429 (shared counter)")
    if api_key:
        status = api_detect(api_key)
        results["rate_limit_api"] = "PASS" if status == 429 else "FAIL"
    else:
        results["rate_limit_api"] = "SKIP"

    # Final report
    step("FINAL REPORT")
    all_pass = True
    for name, status in results.items():
        icon = "[PASS]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[SKIP]"
        print(f"  {icon} {name}")
        if status == "FAIL":
            all_pass = False

    print()
    if all_pass:
        print("  === ALL TESTS PASSED ===")
    else:
        print("  === SOME TESTS FAILED ===")
    
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
