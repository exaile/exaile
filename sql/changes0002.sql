DROP TABLE directories;
CREATE TABLE directories( path PRIMARY KEY, modified INT );
UPDATE version SET version=2;
