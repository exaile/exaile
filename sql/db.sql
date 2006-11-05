-- Initial database schema file for Exaile
CREATE TABLE tracks( path VARCHAR(255) NOT NULL PRIMARY KEY, title VARCHAR(100)
    COLLATE NOCASE, artist VARCHAR(50) COLLATE NOCASE, album VARCHAR(50) COLLATE NOCASE, 
    genre VARCHAR(10) COLLATE NOCASE, year VARCHAR(10), track INT, length INT, bitrate INT, 
    size INT, modified INT, tags MEDIUMTEXT, plays INT DEFAULT 0, rating INT DEFAULT 0, 
    user_rating INT DEFAULT 2, last_played DATE, blacklisted INT DEFAULT 0,
    the_track VARCHAR(40) DEFAULT '', included TINYINT DEFAULT 0 );

-- this table is for ipod tracks
CREATE TABLE ipod_tracks( path VARCHAR(255) NOT NULL PRIMARY KEY, title VARCHAR(100)
    COLLATE NOCASE, artist VARCHAR(50) COLLATE NOCASE, album VARCHAR(50) COLLATE NOCASE, 
    genre VARCHAR(10) COLLATE NOCASE, year VARCHAR(10), track INT, length INT, bitrate INT, 
    size INT, modified INT, tags MEDIUMTEXT, plays INT DEFAULT 0, rating INT DEFAULT 0, 
    user_rating INT DEFAULT 2, last_played DATE, blacklisted INT DEFAULT 0,
    the_track VARCHAR(40) DEFAULT '', included TINYINT DEFAULT 0 );

CREATE TABLE albums( artist VARCHAR(50) NOT NULL COLLATE NOCASE, 
    album VARCHAR(50) NOT NULL COLLATE NOCASE, image VARCHAR(40), large_image VARCHAR(40), 
    amazon_code VARCHAR(40), genre VARCHAR(10), PRIMARY KEY( artist, album ) );

CREATE TABLE playlists( playlist_name VARCHAR(20) COLLATE NOCASE NOT NULL PRIMARY KEY );

CREATE TABLE playlist_items( playlist VARCHAR(20) NOT NULL COLLATE NOCASE, 
    path VARCHAR(255) NOT NULL, PRIMARY KEY( playlist, path ) );

CREATE TABLE radio( radio_name VARCHAR(20) NOT NULL COLLATE NOCASE PRIMARY KEY );

CREATE TABLE radio_items( radio VARCHAR(20) NOT NULL COLLATE NOCASE, title VARCHAR(100), 
    description VARCHAR(100), url VARCHAR(255) NOT NULL, bitrate VARCHAR(10), PRIMARY
    KEY(radio, url) );

CREATE TABLE directories( path VARCHAR(255) NOT NULL PRIMARY KEY, modified INT NOT NULL );

CREATE TABLE podcasts( path VARCHAR(255) NOT NULL PRIMARY KEY, title TEXT, pub_date TEXT, image TEXT, 
    description TEXT );

CREATE TABLE podcast_items( podcast_path VARCHAR(255) NOT NULL, path VARCHAR(255) NOT NULL,
    title TEXT, pub_date TEXT, 
    description TEXT, size INT, length TEXT, PRIMARY KEY(podcast_path, path) );

CREATE TABLE db_version( version TINYINT NOT NULL PRIMARY KEY );
