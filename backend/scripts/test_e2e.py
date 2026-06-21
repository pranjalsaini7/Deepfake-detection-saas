"""End-to-end test: create user, sign in, run detection, verify scan saved."""

import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 1. Create a test user via admin API (auto-confirms email)
print("=== Step 1: Create test user ===")
resp = httpx.post(
    f"{url}/auth/v1/admin/users",
    headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    },
    json={
        "email": "test@deepfake.dev",
        "password": "testpass123",
        "email_confirm": True,
    },
    timeout=15,
)
print(f"Status: {resp.status_code}")
if resp.status_code in (200, 201):
    user = resp.json()
    uid = user.get("id", "unknown")
    print(f"User ID: {uid}")
elif resp.status_code == 422:
    print("User already exists, continuing...")
else:
    print(resp.text[:300])

# 2. Sign in to get a token
print("\n=== Step 2: Sign in ===")
resp2 = httpx.post(
    f"{url}/auth/v1/token?grant_type=password",
    headers={
        "apikey": key,
        "Content-Type": "application/json",
    },
    json={
        "email": "test@deepfake.dev",
        "password": "testpass123",
    },
    timeout=15,
)
print(f"Status: {resp2.status_code}")
if resp2.status_code != 200:
    print(resp2.text[:300])
    exit(1)

session = resp2.json()
token = session["access_token"]
print(f"Got access token: {token[:50]}...")

# 3. Test /detect with the token
print("\n=== Step 3: Run detection ===")
with open(r"..\pexels-manishjangid-18938081.jpg", "rb") as f:
    resp3 = httpx.post(
        "http://localhost:8000/detect",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.jpg", f, "image/jpeg")},
        timeout=60,
    )
print(f"Status: {resp3.status_code}")
print(f"Result: {resp3.text}")

# 4. Check scans table
print("\n=== Step 4: Verify scan in database ===")
resp4 = httpx.get(
    f"{url}/rest/v1/scans?order=created_at.desc&limit=5",
    headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
    },
    timeout=15,
)
print(f"Status: {resp4.status_code}")
scans = resp4.json()
print(f"Scans found: {len(scans)}")
for s in scans:
    print(f"  - {s.get('filename')} | {s.get('label')} | {s.get('confidence')} | {s.get('created_at')}")
