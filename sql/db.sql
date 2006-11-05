-- Initial database schema file for Exaile
CREATE TABLE tracks( path TEXT NOT NULL, 
    title VARCHAR(200) COLLATE NOCASE, 
    artist VARCHAR(200) COLLATE NOCASE, 
    album VARCHAR(200) COLLATE NOCASE, 
    genre VARCHAR(30) COLLATE NOCASE, 
    year VARCHAR(30), 
    track INT, 
    length INT, 
    bitrate INT, 
    size INT, 
    modified BIGINT, 
    tags TEXT, 
    plays INT DEFAULT 0, 
    rating INT DEFAULT 0, 
    user_rating INT DEFAULT 2, 
    last_played TIMESTAMP, 
    blacklisted INT DEFAULT 0,
    the_track VARCHAR(40) DEFAULT '', 
    included INT DEFAULT 0, PRIMARY KEY( path(255) ) );

-- this table is for ipod tracks
CREATE TABLE ipod_tracks( path TEXT NOT NULL, 
    title VARCHAR(200) COLLATE NOCASE, 
    artist VARCHAR(200) COLLATE NOCASE, 
    album VARCHAR(200) COLLATE NOCASE, 
    genre VARCHAR(30) COLLATE NOCASE, 
    year VARCHAR(30), 
    track INT, 
    length INT, 
    bitrate INT, 
    size INT, 
    modified BIGINT, 
    tags TEXT, 
    plays INT DEFAULT 0, 
    rating INT DEFAULT 0, 
    user_rating INT DEFAULT 2, 
    last_played TIMESTAMP, 
    blacklisted INT DEFAULT 0,
    the_track VARCHAR(40) DEFAULT '', 
    included INT DEFAULT 0, PRIMARY KEY( path(255) ) );

CREATE TABLE albums( artist VARCHAR(200) NOT NULL COLLATE NOCASE, 
    album VARCHAR(200) NOT NULL COLLATE NOCASE, 
    image VARCHAR(40), 
    large_image VARCHAR(40), 
    amazon_code VARCHAR(40), 
    genre VARCHAR(30), 
    PRIMARY KEY( artist, album ) );

CREATE TABLE playlists( playlist_name VARCHAR(30) COLLATE NOCASE NOT NULL PRIMARY KEY );

CREATE TABLE playlist_items( playlist VARCHAR(30) NOT NULL COLLATE NOCASE, 
    path TEXT NOT NULL, 
    PRIMARY KEY( playlist, path(255) ) );

CREATE TABLE radio( radio_name VARCHAR(30) NOT NULL COLLATE NOCASE PRIMARY KEY );

CREATE TABLE radio_items( radio VARCHAR(30) NOT NULL COLLATE NOCASE,
    title VARCHAR(100), 
    description VARCHAR(100), 
    url TEXT NOT NULL, 
    bitrate VARCHAR(20), 
    PRIMARY KEY( radio, url(255) ) );

CREATE TABLE directories( path VARCHAR(255) NOT NULL PRIMARY KEY, 
    modified INT NOT NULL );

CREATE TABLE podcasts( path TEXT,
    title TEXT, pub_date TEXT, 
    image TEXT, 
    description TEXT, PRIMARY KEY( path(255) ) );

CREATE TABLE podcast_items( podcast_path TEXT,
    path TEXT NOT NULL, 
    title TEXT, 
    pub_date TEXT, 
    description TEXT, 
    size INT, 
    length TEXT, 
    PRIMARY KEY( podcast_path(255), path(255) ) );

CREATE TABLE db_version( version INT NOT NULL PRIMARY KEY );
