-- Usage tracking table for rate limiting
-- Tracks daily scan count per user with auto-reset on date change

CREATE TABLE IF NOT EXISTS usage (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id),
  daily_scan_count INTEGER DEFAULT 0,
  last_reset_date DATE DEFAULT CURRENT_DATE
);

-- Enable RLS
ALTER TABLE usage ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (backend uses service role key)
-- No user-facing policies needed since users don't query this table directly
