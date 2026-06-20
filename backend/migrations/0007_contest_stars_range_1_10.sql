-- ===========================================================================
-- Widen the contest `stars` rating range from 3–5 to 1–10.
-- ===========================================================================

ALTER TABLE contests DROP CONSTRAINT IF EXISTS contests_stars_range;

ALTER TABLE contests
    ADD CONSTRAINT contests_stars_range
    CHECK (stars IS NULL OR stars BETWEEN 1 AND 10);
