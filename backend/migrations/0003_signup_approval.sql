-- ===========================================================================
-- 0003_signup_approval.sql
-- Adds an admin-approval gate to signup.
--   new column: users.status in ('pending','approved','rejected')
--   new rows default to 'pending' (signup creates pending requests)
--   existing rows are backfilled to 'approved' so current logins keep working
-- ===========================================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected'));

-- Backfill: every row that predates this migration is treated as already
-- approved (otherwise the seed admin would get locked out).
UPDATE users SET status = 'approved' WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);
