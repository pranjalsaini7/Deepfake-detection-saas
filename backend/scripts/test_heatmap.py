"""Test heatmap: sign in, detect with heatmap, save overlay to disk."""

import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Sign in
print("=== Sign in ===")
resp = httpx.post(
    f"{url}/auth/v1/token?grant_type=password",
    headers={"apikey": key, "Content-Type": "application/json"},
    json={"email": "test@deepfake.dev", "password": "testpass123"},
    timeout=15,
)
assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
token = resp.json()["access_token"]
print("Got token.")

# Run detection with heatmap
print("\n=== Detection with heatmap ===")
with open(r"..\pexels-manishjangid-18938081.jpg", "rb") as f:
    resp2 = httpx.post(
        "http://localhost:8000/detect",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.jpg", f, "image/jpeg")},
        timeout=120,
    )

print(f"Status: {resp2.status_code}")
if resp2.status_code != 200:
    print(f"Error: {resp2.text[:500]}")
    exit(1)

data = resp2.json()
print(f"Label: {data['label']}")
print(f"Confidence: {data['confidence']}")
print(f"Heatmap present: {'heatmap' in data and len(data['heatmap']) > 100}")
print(f"Heatmap size: {len(data.get('heatmap', ''))} chars")

# Save heatmap to file for inspection
if data.get("heatmap"):
    heatmap_bytes = base64.b64decode(data["heatmap"])
    out_path = r"..\test_heatmap_output.png"
    with open(out_path, "wb") as f:
        f.write(heatmap_bytes)
    print(f"Heatmap saved to: {out_path}")
