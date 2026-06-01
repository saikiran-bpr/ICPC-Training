-- ===========================================================================
-- Track WHO assigned a problem to a user/team.
--
-- Adds an `assigned_by` column (the actor that created the assignment) to the
-- problem_users and problem_teams junctions, so the contestant view can show
-- "Assigned by <name>".  Existing rows are backfilled to the problem's
-- creator (problems.created_by) — the best available proxy for historic data.
-- ===========================================================================

ALTER TABLE problem_users ADD COLUMN IF NOT EXISTS assigned_by bigint;
ALTER TABLE problem_teams ADD COLUMN IF NOT EXISTS assigned_by bigint;

ALTER TABLE problem_users
    ADD CONSTRAINT problem_users_assigned_by_fkey
    FOREIGN KEY (assigned_by) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE problem_teams
    ADD CONSTRAINT problem_teams_assigned_by_fkey
    FOREIGN KEY (assigned_by) REFERENCES users (id) ON DELETE SET NULL;

-- Backfill historic rows to the problem creator.
UPDATE problem_users pu
   SET assigned_by = p.created_by
  FROM problems p
 WHERE p.id = pu.problem_id
   AND pu.assigned_by IS NULL;

UPDATE problem_teams pt
   SET assigned_by = p.created_by
  FROM problems p
 WHERE p.id = pt.problem_id
   AND pt.assigned_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_problem_users_assigned_by ON problem_users (assigned_by);
CREATE INDEX IF NOT EXISTS idx_problem_teams_assigned_by ON problem_teams (assigned_by);
