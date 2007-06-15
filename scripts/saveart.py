#!/usr/bin/env

from pysqlite2 import dbapi2 as sqlite
import os, sys

(home, musicdir, name) = sys.argv[1:]

db = sqlite.connect('%s/.exaile/music.db' % home)
cur = db.cursor()

cur.execute('SELECT id, name FROM artists')
rows = cur.fetchall()

for row in rows:
    artist = row[1]
    cur.execute('SELECT image, name FROM albums WHERE artist=? AND image IS '
        'NOT NULL AND image != "" AND image != "nocover"', (row[0],))
    if not cur: continue

    for (image, album) in cur:
        if not os.path.isdir('%s/%s/%s' % (musicdir, artist, album)): continue

        target = "%s/%s/%s/%s" % (musicdir, artist, album, name)
        os.system('cp -v %s/.exaile/covers/%s %s' % (home, image,
            target.replace(' ', '\ ').replace('(', '\(').replace(')', '\)')))
        
