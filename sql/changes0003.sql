ALTER TABLE playlists ADD item_limit INT DEFAULT 0;
ALTER TABLE playlists ADD limit_to VARCHAR(30) NULL;
ALTER TABLE playlists ADD sort_by VARCHAR(30) NULL;
UPDATE db_version SET version=3;
