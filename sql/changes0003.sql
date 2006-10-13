-------------------------------------------------------------------------------
-- Changes file for Exaile 0.2.5
--
-- * Adds a "the_track" to the tracks table, a storage place for tracks where
--   the artist begins with "The " so that it can be sorted without "The "
--   - Example, "The Beatles" would show up in the B's in the collection
--   - panel
-------------------------------------------------------------------------------
ALTER TABLE tracks ADD the_track DEFAULT '';
ALTER TABLE tracks ADD included DEFAULT 0;
UPDATE version SET version=3;
