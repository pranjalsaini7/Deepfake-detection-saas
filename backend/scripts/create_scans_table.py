"""Create the 'scans' table in Supabase via the pg-meta query endpoint."""

import httpx
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

SQL = """
CREATE TABLE IF NOT EXISTS public.scans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    filename text NOT NULL,
    label text NOT NULL,
    confidence double precision NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.scans ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'Users can view own scans'
    ) THEN
        EXECUTE 'CREATE POLICY "Users can view own scans" ON public.scans FOR SELECT USING (auth.uid() = user_id)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'Service role can insert scans'
    ) THEN
        EXECUTE 'CREATE POLICY "Service role can insert scans" ON public.scans FOR INSERT WITH CHECK (true)';
    END IF;
END
$$;
"""


def main():
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Try the pg-meta query endpoint (used by Supabase Studio)
    resp = httpx.post(
        f"{url}/pg/query",
        headers=headers,
        json={"query": SQL},
        timeout=30,
    )

    print(f"Status: {resp.status_code}")
    if resp.status_code in (200, 201):
        print("Table 'scans' created successfully!")
    else:
        print(f"Response: {resp.text[:500]}")
        print("\nIf this failed, please run the following SQL in your Supabase SQL Editor:")
        print(SQL)


if __name__ == "__main__":
    main()
