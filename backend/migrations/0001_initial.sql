-- ICPC Training Problem Repository — Postgres schema (Supabase)
--
-- Ported from schema.sql with these substitutions per the Supabase
-- best-practices skill:
--   • INTEGER PRIMARY KEY AUTOINCREMENT → bigint generated always as identity
--   • TEXT date/time columns             → timestamptz
--   • Every foreign-key column has an index (HIGH-impact rule).
--   • All identifiers are lowercase snake_case (default Postgres folding).
--
-- Pragmatic carve-outs (minimise diffs to the SQLite-flavoured Flask code):
--   • Boolean-style flag columns (is_active, is_bank, from_contest,
--     via_contest, editorial_found) use `smallint` instead of `boolean` so
--     the existing `WHERE is_active = 1` filters and `1 if v else 0` writes
--     keep working untouched.  One byte per row larger than `boolean`.
--   • `tags` stays `text` (a JSON-stringified array, populated via
--     `json.dumps(...)` in the Flask code).  Migrate to `jsonb` later if we
--     ever need indexed JSON queries.
--
-- RLS intentionally NOT enabled: Flask is the sole DB client and enforces
-- per-user filtering in the query layer.  Revisit if a frontend ever talks
-- to the DB directly (e.g. via Supabase Auth + anon key).
--
-- Re-runnable: every CREATE uses IF NOT EXISTS / OR REPLACE / DO blocks for
-- constraints so applying twice is safe.

-- ===========================================================================
-- problems
-- ===========================================================================
CREATE TABLE IF NOT EXISTS problems (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name              text    NOT NULL,
    url               text    NOT NULL UNIQUE,

    -- Source
    platform          text    NOT NULL,
    contest_name      text,
    contest_type      text,
    contest_year      integer,
    problem_index     text,

    -- Difficulty
    rating            integer,
    difficulty        text,

    -- Categorization
    topic             text,
    sub_topic         text,
    tags              text,                          -- JSON array as string

    -- Training metadata
    importance        text,
    suggested_role    text,
    prerequisites     text,
    key_idea          text,
    editorial_url     text,
    time_limit_ms     integer,
    memory_limit_mb   integer,

    -- Tracking
    status            text    DEFAULT 'Todo',
    assigned_to       text,
    assigned_user_id  bigint,
    assigned_team_id  bigint,
    created_by        bigint,
    is_bank           smallint NOT NULL DEFAULT 0,
    from_contest      smallint NOT NULL DEFAULT 0,
    notes             text,

    -- Timestamps
    date_added        timestamptz NOT NULL DEFAULT now(),
    date_updated      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_problems_platform        ON problems (platform);
CREATE INDEX IF NOT EXISTS idx_problems_topic           ON problems (topic);
CREATE INDEX IF NOT EXISTS idx_problems_rating          ON problems (rating);
CREATE INDEX IF NOT EXISTS idx_problems_importance      ON problems (importance);
CREATE INDEX IF NOT EXISTS idx_problems_status          ON problems (status);
CREATE INDEX IF NOT EXISTS idx_problems_assigned_user   ON problems (assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_problems_assigned_team   ON problems (assigned_team_id);
CREATE INDEX IF NOT EXISTS idx_problems_created_by      ON problems (created_by);
CREATE INDEX IF NOT EXISTS idx_problems_is_bank         ON problems (is_bank);
CREATE INDEX IF NOT EXISTS idx_problems_from_contest    ON problems (from_contest);

-- Auto-update date_updated on row change
CREATE OR REPLACE FUNCTION trg_set_date_updated() RETURNS trigger AS $$
BEGIN
    NEW.date_updated := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_problems_updated ON problems;
CREATE TRIGGER trg_problems_updated
BEFORE UPDATE ON problems
FOR EACH ROW EXECUTE FUNCTION trg_set_date_updated();

-- ===========================================================================
-- users
-- ===========================================================================
CREATE TABLE IF NOT EXISTS users (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email          text    NOT NULL UNIQUE,           -- lowercased in app layer
    password_hash  text    NOT NULL,
    name           text    NOT NULL,
    role           text    NOT NULL CHECK (role IN ('Admin','Coach','Contestant')),
    handle         text,
    institution    text,
    year_of_study  integer,
    is_active      smallint NOT NULL DEFAULT 1,
    date_joined    timestamptz NOT NULL DEFAULT now(),
    last_login     timestamptz
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

-- ===========================================================================
-- teams
-- ===========================================================================
CREATE TABLE IF NOT EXISTS teams (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         text    NOT NULL UNIQUE,
    institution  text,
    description  text,
    is_active    smallint NOT NULL DEFAULT 1,
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   bigint,
    CONSTRAINT teams_created_by_fkey
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_teams_active     ON teams (is_active);
CREATE INDEX IF NOT EXISTS idx_teams_created_by ON teams (created_by);

-- ===========================================================================
-- team_members  (App enforces: per team max 3 Member + 1 Reserve)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS team_members (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id       bigint  NOT NULL,
    user_id       bigint  NOT NULL,
    role_in_team  text    NOT NULL CHECK (role_in_team IN ('Member','Reserve')),
    joined_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT team_members_team_id_fkey
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT team_members_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT team_members_team_user_unique UNIQUE (team_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members (team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members (user_id);

-- ===========================================================================
-- team_coaches
-- ===========================================================================
CREATE TABLE IF NOT EXISTS team_coaches (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_id      bigint  NOT NULL,
    user_id      bigint  NOT NULL,
    assigned_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT team_coaches_team_id_fkey
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT team_coaches_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT team_coaches_team_user_unique UNIQUE (team_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_team_coaches_team ON team_coaches (team_id);
CREATE INDEX IF NOT EXISTS idx_team_coaches_user ON team_coaches (user_id);

-- ===========================================================================
-- problem_teams (many-to-many)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS problem_teams (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    problem_id   bigint  NOT NULL,
    team_id      bigint  NOT NULL,
    assigned_at  timestamptz NOT NULL DEFAULT now(),
    via_contest  smallint NOT NULL DEFAULT 0,
    CONSTRAINT problem_teams_problem_id_fkey
        FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE,
    CONSTRAINT problem_teams_team_id_fkey
        FOREIGN KEY (team_id)    REFERENCES teams (id)    ON DELETE CASCADE,
    CONSTRAINT problem_teams_problem_team_unique UNIQUE (problem_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_problem_teams_problem ON problem_teams (problem_id);
CREATE INDEX IF NOT EXISTS idx_problem_teams_team    ON problem_teams (team_id);

-- ===========================================================================
-- problem_users (many-to-many)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS problem_users (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    problem_id   bigint  NOT NULL,
    user_id      bigint  NOT NULL,
    assigned_at  timestamptz NOT NULL DEFAULT now(),
    via_contest  smallint NOT NULL DEFAULT 0,
    CONSTRAINT problem_users_problem_id_fkey
        FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE,
    CONSTRAINT problem_users_user_id_fkey
        FOREIGN KEY (user_id)    REFERENCES users (id)    ON DELETE CASCADE,
    CONSTRAINT problem_users_problem_user_unique UNIQUE (problem_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_problem_users_problem ON problem_users (problem_id);
CREATE INDEX IF NOT EXISTS idx_problem_users_user    ON problem_users (user_id);

-- ===========================================================================
-- problem_attempts
-- ===========================================================================
CREATE TABLE IF NOT EXISTS problem_attempts (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    problem_id      bigint  NOT NULL,
    user_id         bigint  NOT NULL,
    attempt_status  text,
    problem_faced   text,
    time_spent_min  integer,
    notes           text,
    attempt_phase   text,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT problem_attempts_problem_id_fkey
        FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE,
    CONSTRAINT problem_attempts_user_id_fkey
        FOREIGN KEY (user_id)    REFERENCES users (id)    ON DELETE CASCADE,
    CONSTRAINT problem_attempts_problem_user_unique UNIQUE (problem_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_problem_attempts_problem ON problem_attempts (problem_id);
CREATE INDEX IF NOT EXISTS idx_problem_attempts_user    ON problem_attempts (user_id);
CREATE INDEX IF NOT EXISTS idx_problem_attempts_status  ON problem_attempts (attempt_status);

-- ===========================================================================
-- contests
-- ===========================================================================
CREATE TABLE IF NOT EXISTS contests (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name                text    NOT NULL,
    platform            text,
    contest_type        text,
    contest_year        integer,
    url                 text,
    notes               text,
    tutorial_pdf        text,
    tutorial_translated text,
    tutorial_lang       text,
    cf_stars            numeric(3,1),
    ucup_stars          numeric(3,1),
    created_by          bigint,
    date_added          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contests_platform   ON contests (platform);
CREATE INDEX IF NOT EXISTS idx_contests_created_by ON contests (created_by);

-- ===========================================================================
-- contest_users / contest_teams
-- ===========================================================================
CREATE TABLE IF NOT EXISTS contest_users (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contest_id  bigint  NOT NULL,
    user_id     bigint  NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contest_users_contest_id_fkey
        FOREIGN KEY (contest_id) REFERENCES contests (id) ON DELETE CASCADE,
    CONSTRAINT contest_users_user_id_fkey
        FOREIGN KEY (user_id)    REFERENCES users (id)    ON DELETE CASCADE,
    CONSTRAINT contest_users_contest_user_unique UNIQUE (contest_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_contest_users_contest ON contest_users (contest_id);
CREATE INDEX IF NOT EXISTS idx_contest_users_user    ON contest_users (user_id);

CREATE TABLE IF NOT EXISTS contest_teams (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contest_id  bigint  NOT NULL,
    team_id     bigint  NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contest_teams_contest_id_fkey
        FOREIGN KEY (contest_id) REFERENCES contests (id) ON DELETE CASCADE,
    CONSTRAINT contest_teams_team_id_fkey
        FOREIGN KEY (team_id)    REFERENCES teams (id)    ON DELETE CASCADE,
    CONSTRAINT contest_teams_contest_team_unique UNIQUE (contest_id, team_id)
);
CREATE INDEX IF NOT EXISTS idx_contest_teams_contest ON contest_teams (contest_id);
CREATE INDEX IF NOT EXISTS idx_contest_teams_team    ON contest_teams (team_id);

-- ===========================================================================
-- contest_problems (many-to-many)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS contest_problems (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contest_id  bigint  NOT NULL,
    problem_id  bigint  NOT NULL,
    order_idx   integer,
    CONSTRAINT contest_problems_contest_id_fkey
        FOREIGN KEY (contest_id) REFERENCES contests (id) ON DELETE CASCADE,
    CONSTRAINT contest_problems_problem_id_fkey
        FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE,
    CONSTRAINT contest_problems_contest_problem_unique UNIQUE (contest_id, problem_id)
);
CREATE INDEX IF NOT EXISTS idx_contest_problems_contest ON contest_problems (contest_id);
CREATE INDEX IF NOT EXISTS idx_contest_problems_problem ON contest_problems (problem_id);

-- ===========================================================================
-- problem_tutorials
-- ===========================================================================
CREATE TABLE IF NOT EXISTS problem_tutorials (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    problem_id          bigint  NOT NULL UNIQUE,
    slug                text    NOT NULL UNIQUE,
    status              text    NOT NULL DEFAULT 'queued',
    generated_at        timestamptz,
    generator_version   text,
    error_message       text,
    student_md_path     text,
    teacher_md_path     text,
    student_pdf_path    text,
    teacher_pdf_path    text,
    key_insight         text,
    rung_count          integer,
    mcq_count           integer,
    snippet_count       integer,
    editorial_found     smallint,
    research_confidence text,
    CONSTRAINT problem_tutorials_problem_id_fkey
        FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_problem_tutorials_problem ON problem_tutorials (problem_id);
CREATE INDEX IF NOT EXISTS idx_problem_tutorials_status  ON problem_tutorials (status);

-- ===========================================================================
-- tutorial_unlocks
-- ===========================================================================
CREATE TABLE IF NOT EXISTS tutorial_unlocks (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id              bigint  NOT NULL,
    problem_id           bigint  NOT NULL,
    unlocked_at          timestamptz NOT NULL DEFAULT now(),
    claimed_minutes      integer,
    threshold_minutes    integer,
    CONSTRAINT tutorial_unlocks_user_problem_unique UNIQUE (user_id, problem_id),
    CONSTRAINT tutorial_unlocks_user_id_fkey
        FOREIGN KEY (user_id)    REFERENCES users (id)    ON DELETE CASCADE,
    CONSTRAINT tutorial_unlocks_problem_id_fkey
        FOREIGN KEY (problem_id) REFERENCES problems (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tutorial_unlocks_user    ON tutorial_unlocks (user_id);
CREATE INDEX IF NOT EXISTS idx_tutorial_unlocks_problem ON tutorial_unlocks (problem_id);
