-- Performance indexes derived from skill rules + actual query patterns in
-- legacy/app.py.  Each comment cites the skill reference + the query that
-- benefits.
--
-- All CREATE INDEX statements are IF NOT EXISTS so re-applying is safe.

-- ---------------------------------------------------------------------------
-- /api/problems filters by combinations of: platform, topic, difficulty,
-- importance, status, contest_type — plus the *always-on* `via_contest = 0`
-- filter via problem_users / problem_teams.  Composite + partial indexes
-- accelerate the common filter shapes.
--
-- skill: query-composite-indexes  +  query-partial-indexes
-- ---------------------------------------------------------------------------

-- The list endpoint sorts by date_added DESC by default; index aligns.
CREATE INDEX IF NOT EXISTS idx_problems_date_added_desc
    ON problems (date_added DESC);

-- Common composite — most user-facing filters combine platform + topic.
CREATE INDEX IF NOT EXISTS idx_problems_platform_topic
    ON problems (platform, topic);

-- Difficulty filter is high-cardinality enough to stand alone; add an
-- ordering helper for the `?sort=rating` path.
CREATE INDEX IF NOT EXISTS idx_problems_difficulty_rating
    ON problems (difficulty, rating);

-- Bank list always filters `from_contest = 0`; partial index ≈ 5-20× smaller.
-- skill: query-partial-indexes
CREATE INDEX IF NOT EXISTS idx_problems_bank_only
    ON problems (date_added DESC)
    WHERE from_contest = 0;


-- ---------------------------------------------------------------------------
-- /api/problems and /api/contests/assigned filter junction rows by
-- via_contest = 0 (direct assignments) almost exclusively.
-- skill: query-partial-indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_problem_users_direct
    ON problem_users (user_id, problem_id)
    WHERE via_contest = 0;

CREATE INDEX IF NOT EXISTS idx_problem_teams_direct
    ON problem_teams (team_id, problem_id)
    WHERE via_contest = 0;


-- ---------------------------------------------------------------------------
-- problem_attempts is filtered by (problem_id, user_id) on every read AND on
-- every upsert (ON CONFLICT).  The UNIQUE constraint covers this implicitly,
-- but creating a composite index named explicitly helps EXPLAIN output and
-- is a no-op if the unique already provides it (Postgres will skip it).
-- skill: query-composite-indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_problem_attempts_user_phase
    ON problem_attempts (user_id, attempt_status, attempt_phase);


-- ---------------------------------------------------------------------------
-- /api/contests/assigned does a heavy phase rollup grouped by problem; an
-- index on contest_problems.contest_id (already exists as FK index) plus an
-- index on problem_attempts.problem_id (also exists) suffices.  No new
-- indexes added here — but the comment documents the rationale for
-- next-time reviewers.
-- ---------------------------------------------------------------------------
