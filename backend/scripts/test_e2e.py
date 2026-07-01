"""End-to-end test: API key generation + /api/detect endpoint."""

import httpx
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
API_BASE = "http://localhost:8000"

# ── Step 1: Sign in ──────────────────────────────────────────────────
print("=== Step 1: Sign in ===")
resp = httpx.post(
    f"{url}/auth/v1/token?grant_type=password",
    headers={"apikey": key, "Content-Type": "application/json"},
    json={"email": "test@deepfake.dev", "password": "testpass123"},
    timeout=15,
)
assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
token = resp.json()["access_token"]
print("Signed in OK.")

# ── Step 2: Generate API key ─────────────────────────────────────────
print("\n=== Step 2: Generate API key ===")
resp = httpx.post(
    f"{API_BASE}/api-keys/generate",
    headers={"Authorization": f"Bearer {token}"},
    timeout=15,
)
assert resp.status_code == 200, f"Key generation failed: {resp.text}"
key_data = resp.json()
raw_key = key_data["raw_key"]
print(f"Generated key: {raw_key[:12]}...")
print(f"Prefix: {key_data['key_prefix']}")

# ── Step 3: List API keys ────────────────────────────────────────────
print("\n=== Step 3: List API keys ===")
resp = httpx.get(
    f"{API_BASE}/api-keys",
    headers={"Authorization": f"Bearer {token}"},
    timeout=15,
)
assert resp.status_code == 200
keys = resp.json()["keys"]
print(f"Total keys: {len(keys)}")

# ── Step 4: Test /api/detect with valid key ──────────────────────────
print("\n=== Step 4: /api/detect with valid key ===")
img_path = os.path.join(os.path.dirname(__file__), "..", "..", "pexels-manishjangid-18938081.jpg")
with open(img_path, "rb") as f:
    resp = httpx.post(
        f"{API_BASE}/api/detect",
        headers={"X-API-Key": raw_key},
        files={"file": ("test.jpg", f, "image/jpeg")},
        timeout=300,
    )
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Label: {data['label']}, Confidence: {data['confidence']}%")
    print(f"Heatmap present: {bool(data.get('heatmap'))}")
else:
    print(f"Error: {resp.text[:300]}")

# ── Step 5: Test /api/detect with INVALID key ────────────────────────
print("\n=== Step 5: /api/detect with invalid key ===")
resp = httpx.post(
    f"{API_BASE}/api/detect",
    headers={"X-API-Key": "sk_invalid_key_12345"},
    files={"file": ("test.jpg", b"fake", "image/jpeg")},
    timeout=15,
)
print(f"Status: {resp.status_code} (expected 401)")
print(f"Response: {resp.json()}")

# ── Step 6: Test /api/detect with NO key ─────────────────────────────
print("\n=== Step 6: /api/detect with no key ===")
resp = httpx.post(
    f"{API_BASE}/api/detect",
    files={"file": ("test.jpg", b"fake", "image/jpeg")},
    timeout=15,
)
print(f"Status: {resp.status_code} (expected 401)")
print(f"Response: {resp.json()}")

print("\n=== ALL TESTS COMPLETE ===")
