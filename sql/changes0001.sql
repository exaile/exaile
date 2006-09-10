CREATE TABLE podcasts( path TEXT NOT NULL PRIMARY KEY, title TEXT, pub_date TEXT, image TEXT, description TEXT );
CREATE TABLE podcast_items( podcast_path TEXT, path TEXT, title TEXT, pub_date TEXT, description TEXT, size INT, length TEXT );
INSERT INTO version VALUES( 1 );
