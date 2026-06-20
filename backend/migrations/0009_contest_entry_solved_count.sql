-- ===========================================================================
-- Add a "problems solved" count to each member's contest entry, so members
-- can report how many problems they solved in the contest.
-- ===========================================================================

ALTER TABLE contest_member_entries
    ADD COLUMN IF NOT EXISTS solved_count integer NOT NULL DEFAULT 0;

ALTER TABLE contest_member_entries
    ADD CONSTRAINT contest_member_entries_solved_count_check
    CHECK (solved_count >= 0);
