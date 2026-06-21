"""
Supabase client helpers for the backend.

Uses the service-role key to:
  - Verify user auth tokens via GoTrue
  - Insert scan records into the 'scans' table
"""

import os
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
