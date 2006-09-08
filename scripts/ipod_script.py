#!/usr/bin/env python

import os, os.path, sys
from pysqlite2 import dbapi2 as sqlite

music = sys.argv[1]

if not music:
    print "Usage: ./ipod_script [music_location]"
    sys.exit(1)

SETTINGS_DIR = os.getenv("HOME") + "/.exaile"
IMAGE_DIR = SETTINGS_DIR + "/covers"
SAVE_DIR = "./ipod_covers"
if not os.path.isdir(SAVE_DIR): os.mkdir(SAVE_DIR)

print SETTINGS_DIR + "/music.db"
db = sqlite.connect(SETTINGS_DIR + "/music.db")
cur = db.cursor()
cur.execute("SELECT artist, album, image FROM albums WHERE image!=''")

for (artist, album, image) in cur:
    try:
        path = "%s/%s/%s" % (music, artist, album)
        if os.path.isdir(path):
            target = "%s/%s/%s/folder.jpg" % (music, artist, album)
            target = target.replace(" ", "\\ ")
            string = "ln -sf %s/%s %s" % (IMAGE_DIR, image, target)
            print string
            os.system(string)
            newtarget = "%s/%s - %s.jpg" % (SAVE_DIR, artist, album)
            newtarget = newtarget.replace(" ", "\\ ")
            string = "ln -sf %s/%s %s" % (IMAGE_DIR, image, newtarget)
            os.system(string)

            #print "Found %s by %s" % (album, artist)
        else:
            print path
            print "Could not find %s by %s" % (artist, album)
    except:
        pass
