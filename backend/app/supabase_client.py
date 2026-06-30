"""
Supabase client helpers for the backend.

Uses the service-role key to:
  - Verify user auth tokens via GoTrue
  - Insert scan records into the 'scans' table
  - Manage API keys (create, verify, list, update last_used_at)
"""

import os
import hashlib
import secrets
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in backend/.env"
    )

# ── Headers for service-role API calls ───────────────────────────────
_headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


async def get_user_from_token(access_token: str) -> dict | None:
    """
    Verify a user's JWT by calling Supabase GoTrue's /auth/v1/user endpoint.
    Returns the user dict if valid, or None if invalid/expired.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
        )

    if resp.status_code == 200:
        return resp.json()
    return None


async def insert_scan(
    user_id: str,
    filename: str,
    label: str,
    confidence: float,
) -> dict:
    """
    Insert a scan record into the 'scans' table via PostgREST.
    Uses the service-role key to bypass RLS.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/scans",
            headers={
                **_headers,
                "Prefer": "return=representation",
            },
            json={
                "user_id": user_id,
                "filename": filename,
                "label": label,
                "confidence": confidence,
            },
        )

    if resp.status_code not in (200, 201):
        print(f"[SUPABASE] Failed to insert scan: {resp.status_code} {resp.text}")
        return {}

    data = resp.json()
    return data[0] if data else {}


# ── API Key helpers ──────────────────────────────────────────────────

def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_raw_api_key() -> str:
    """Generate a raw API key: sk_ + 32 URL-safe random bytes."""
    return "sk_" + secrets.token_urlsafe(32)


async def create_api_key(user_id: str) -> dict:
    """
    Generate a new API key for a user.
    Returns {"raw_key": str, "key_prefix": str, "id": str}.
    The raw key is returned ONLY ONCE — only the hash is stored.
    """
    raw_key = generate_raw_api_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:8] + "..."

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/api_keys",
            headers={
                **_headers,
                "Prefer": "return=representation",
            },
            json={
                "user_id": user_id,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
            },
        )

    if resp.status_code not in (200, 201):
        print(f"[SUPABASE] Failed to create API key: {resp.status_code} {resp.text}")
        return {}

    data = resp.json()
    record = data[0] if data else {}

    return {
        "raw_key": raw_key,
        "key_prefix": key_prefix,
        "id": record.get("id"),
        "created_at": record.get("created_at"),
    }


async def verify_api_key(raw_key: str) -> dict | None:
    """
    Verify an API key by hashing it and looking up in api_keys table.
    Returns the key record if valid and active, or None.
    """
    key_hash = hash_api_key(raw_key)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/api_keys",
            headers=_headers,
            params={
                "key_hash": f"eq.{key_hash}",
                "is_active": "eq.true",
                "select": "id,user_id,key_prefix,created_at,last_used_at",
            },
        )

    if resp.status_code != 200:
        print(f"[SUPABASE] API key lookup failed: {resp.status_code} {resp.text}")
        return None

    data = resp.json()
    if not data:
        return None

    key_record = data[0]

    # Update last_used_at
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/api_keys?id=eq.{key_record['id']}",
            headers=_headers,
            json={"last_used_at": "now()"},
        )

    return key_record


async def list_api_keys(user_id: str) -> list:
    """
    List all API keys for a user (only prefixes, never raw keys).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/api_keys",
            headers=_headers,
            params={
                "user_id": f"eq.{user_id}",
                "select": "id,key_prefix,created_at,last_used_at,is_active",
                "order": "created_at.desc",
            },
        )

    if resp.status_code != 200:
        return []

    return resp.json()


async def revoke_api_key(key_id: str, user_id: str) -> bool:
    """Deactivate an API key."""
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/api_keys?id=eq.{key_id}&user_id=eq.{user_id}",
            headers=_headers,
            json={"is_active": False},
        )

    return resp.status_code == 200 or resp.status_code == 204
