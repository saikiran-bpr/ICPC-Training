-- ===========================================================================
-- Drop the contest_name / contest_year / problem_index columns from `problems`.
--
-- These were optional source-metadata fields on bank problems that the
-- "New problem" form exposed.  They've been removed from the UI and API, so
-- the columns are dropped here.  IF EXISTS keeps this idempotent for fresh DBs.
--
-- NOTE: the separate `contests` table keeps its own `contest_year` column —
-- this migration only touches `problems`.
-- ===========================================================================

ALTER TABLE problems DROP COLUMN IF EXISTS contest_name;
ALTER TABLE problems DROP COLUMN IF EXISTS contest_year;
ALTER TABLE problems DROP COLUMN IF EXISTS problem_index;
