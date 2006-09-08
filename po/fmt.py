#!/usr/bin/env python

import os, traceback

for file in os.listdir("."):
    if file.endswith(".po"):
        dir = file.replace(".po", "")
        if not os.path.isdir(dir): 
            try:
                os.makedirs("%s/LC_MESSAGES" % (dir))
            except:
                traceback.print_exc()
        newfile = file.replace(".po", ".mo")
        os.system("msgfmt %s -o %s/LC_MESSAGES/%s" % (file, dir, newfile))

print "Done generating localization files."
