-- Initial database schema file for Exaile
CREATE TABLE paths( id INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL );
CREATE TABLE tracks( path INT NOT NULL,
    title VARCHAR(200), 
    artist INT NOT NULL, 
    album INT NOT NULL,
    genre VARCHAR(30), 
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
    last_played DATETIME, 
    time_added DATETIME,
    blacklisted INT DEFAULT 0,
    type TINYINT DEFAULT 0,
    included INT DEFAULT 0, PRIMARY KEY( path ) );
CREATE INDEX album_index ON tracks(album);
CREATE INDEX artist_index ON tracks(artist);

CREATE TABLE artists( id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE );

CREATE TABLE albums( id INTEGER NOT NULL PRIMARY KEY,
    artist INT NOT NULL, 
    name VARCHAR(50) NOT NULL, 
    image VARCHAR(40));

CREATE UNIQUE INDEX albums_artist ON albums(artist, name);

CREATE UNIQUE INDEX album_artist_index ON albums( artist, name );

CREATE TABLE playlists( id INTEGER NOT NULL PRIMARY KEY, 
    name VARCHAR(30) NOT NULL UNIQUE, 
    type TINYINT DEFAULT 0 );

CREATE TABLE playlist_items( playlist INT NOT NULL,
    path INT NOT NULL,
    PRIMARY KEY( playlist, path ) );

CREATE TABLE smart_playlist_items( playlist INT NOT NULL,
    operator VARCHAR(40) NOT NULL,
    col VARCHAR(255) NOT NULL, 
    PRIMARY KEY( playlist, col ) );

CREATE TABLE radio( id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE );

CREATE TABLE radio_items( radio INT NOT NULL,
    PATH INT NOT NULL, 
    title VARCHAR(100), 
    description VARCHAR(100), 
    bitrate VARCHAR(20), 
    PRIMARY KEY( radio, path ) );

CREATE TABLE directories( path INT NOT NULL PRIMARY KEY,
    modified INT NOT NULL );

CREATE TABLE podcasts( path INT NOT NULL PRIMARY KEY,
    title TEXT, 
    pub_date TEXT, 
    image TEXT, 
    description TEXT );

CREATE TABLE podcast_items( podcast_path INT NOT NULL,
    path INT NOT NULL, 
    title TEXT, 
    pub_date TEXT, 
    description TEXT, 
    size INT, 
    length TEXT, 
    PRIMARY KEY( podcast_path, path ) );

CREATE TABLE db_version( version INT NOT NULL PRIMARY KEY );
