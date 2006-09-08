CREATE TABLE tracks( path PRIMARY KEY, title COLLATE NOCASE, artist COLLATE NOCASE, album COLLATE NOCASE, genre COLLATE NOCASE, year, track INT, length INT, bitrate INT, size INT, modified INT, tags, plays INT DEFAULT 0, rating INT DEFAULT 0, user_rating INT DEFAULT 2, blacklisted INT DEFAULT 0 );
CREATE TABLE albums( artist COLLATE NOCASE, album COLLATE NOCASE, image, large_image, amazon_code, genre, PRIMARY KEY( artist, album ) );
CREATE TABLE playlists( playlist_name COLLATE NOCASE );
CREATE TABLE playlist_items( playlist COLLATE NOCASE, path, PRIMARY KEY( playlist, path ) );
CREATE TABLE radio( radio_name COLLATE NOCASE );
CREATE TABLE radio_items( radio COLLATE NOCASE, title, description, url, bitrate );
CREATE TABLE directories( path, modified INT );
CREATE TABLE version( version );
