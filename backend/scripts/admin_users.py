"""
Admin script to list and confirm Supabase users.
Uses the service role key for admin operations.
"""
import httpx
import sys
import os

# Load from env
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

def list_users():
    r = httpx.get(f"{SUPABASE_URL}/auth/v1/admin/users", headers=headers)
    if r.status_code != 200:
        print(f"Error: {r.status_code} {r.text}")
        return []
    data = r.json()
    users = data.get("users", [])
    print(f"Found {len(users)} users:")
    for u in users:
        confirmed = u.get("email_confirmed_at", "Not confirmed")
        print(f"  {u['email']} | confirmed={confirmed} | id={u['id']}")
    return users

def confirm_user(user_id):
    """Confirm a user's email by updating via admin API."""
    r = httpx.put(
        f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
        headers=headers,
        json={"email_confirm": True},
    )
    if r.status_code == 200:
        print(f"  [OK] User {user_id} email confirmed!")
        return True
    else:
        print(f"  [FAIL] Failed to confirm: {r.status_code} {r.text}")
        return False

if __name__ == "__main__":
    users = list_users()
    
    if "--confirm-all" in sys.argv:
        print("\nConfirming all unconfirmed users...")
        for u in users:
            if not u.get("email_confirmed_at"):
                confirm_user(u["id"])
    elif "--confirm" in sys.argv and len(sys.argv) > sys.argv.index("--confirm") + 1:
        email = sys.argv[sys.argv.index("--confirm") + 1]
        for u in users:
            if u["email"] == email:
                confirm_user(u["id"])
                break
        else:
            print(f"User {email} not found")
