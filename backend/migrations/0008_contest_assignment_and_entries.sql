-- ===========================================================================
-- Contest assignment metadata + per-member status & reflections.
--
--   • contest_teams gains an optional due_date plus assigner tracking, so a
--     coach/admin can give a team a deadline when assigning a contest.
--   • contest_member_entries — one row per (contest, user): the member's own
--     status (Not started / Attempted / Completed) and reflection notes
--     (how it felt, what mistakes they made).  The whole team + coaches/admins
--     can read these; each member edits only their own row.
-- ===========================================================================

-- --- contest_teams: deadline + who assigned ---------------------------------
ALTER TABLE contest_teams ADD COLUMN IF NOT EXISTS due_date date;
ALTER TABLE contest_teams ADD COLUMN IF NOT EXISTS assigned_by bigint;
ALTER TABLE contest_teams ADD COLUMN IF NOT EXISTS assigned_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE contest_teams
    ADD CONSTRAINT contest_teams_assigned_by_fkey
    FOREIGN KEY (assigned_by) REFERENCES users (id) ON DELETE SET NULL;

-- --- contest_member_entries: status + reflection ----------------------------
CREATE TABLE IF NOT EXISTS contest_member_entries (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contest_id  bigint NOT NULL,
    user_id     bigint NOT NULL,
    status      text   NOT NULL DEFAULT 'Not started',
    feedback    text,
    mistakes    text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contest_member_entries_contest_id_fkey
        FOREIGN KEY (contest_id) REFERENCES contests (id) ON DELETE CASCADE,
    CONSTRAINT contest_member_entries_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT contest_member_entries_contest_user_unique
        UNIQUE (contest_id, user_id),
    CONSTRAINT contest_member_entries_status_check
        CHECK (status IN ('Not started', 'Attempted', 'Completed'))
);

CREATE INDEX IF NOT EXISTS idx_contest_member_entries_contest
    ON contest_member_entries (contest_id);
CREATE INDEX IF NOT EXISTS idx_contest_member_entries_user
    ON contest_member_entries (user_id);
