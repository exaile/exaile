-------------------------------------------------------------------------------
-- Changes file for Exaile 0.2.5
--
-- * Adds a "the_track" to the tracks table, a storage place for tracks where
--   the artist begins with "The " so that it can be sorted without "The "
--   - Example, "The Beatles" would show up in the B's in the collection
--   - panel
-- * Adds an id to sort by in the podcast_items table
-------------------------------------------------------------------------------
ALTER TABLE tracks ADD the_track DEFAULT '';
DROP TABLE podcast_items;
CREATE TABLE podcast_items( id INTEGER NOT NULL PRIMARY KEY, podcast_path TEXT, path TEXT, title TEXT, pub_date TEXT, description TEXT, size INT, length TEXT );
UPDATE version SET version=3;
