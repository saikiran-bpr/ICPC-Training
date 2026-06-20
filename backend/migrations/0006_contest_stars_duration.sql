-- ===========================================================================
-- Add a manual difficulty rating and contest length to `contests`.
--
--   • stars            — coach-assigned difficulty: 3, 4 or 5 stars.
--   • duration_minutes — length of the contest, in minutes.
--
-- Both are optional (nullable); existing rows are left NULL.
-- ===========================================================================

ALTER TABLE contests ADD COLUMN IF NOT EXISTS stars smallint;
ALTER TABLE contests ADD COLUMN IF NOT EXISTS duration_minutes integer;

ALTER TABLE contests
    ADD CONSTRAINT contests_stars_range
    CHECK (stars IS NULL OR stars BETWEEN 3 AND 5);

ALTER TABLE contests
    ADD CONSTRAINT contests_duration_minutes_positive
    CHECK (duration_minutes IS NULL OR duration_minutes > 0);
