ALTER TABLE TRACKS ADD encoding VARCHAR(15);
UPDATE db_version SET version=1; 
