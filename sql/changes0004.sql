ALTER TABLE playlist_items ADD sort_index INTEGER NULL;
UPDATE db_version SET version=4;
