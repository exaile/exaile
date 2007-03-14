ALTER TABLE albums ADD amazon_image TINYINT DEFAULT 0;
UPDATE albums SET amazon_image=1;
UPDATE db_version SET version=2;
