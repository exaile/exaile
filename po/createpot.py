#!/usr/bin/env python

import os, sys

if len(sys.argv) <= 1:
    os.system("intltool-extract --type=gettext/glade exaile.glade")
    os.system("xgettext -k_ -kN_ -o messages.pot *.py xl/*.py exaile.glade.h")
    print "Now edit messages.pot, save it as <locale>.po, and send it" \
        " to arolsen@gmail.com.\nThanks!\n"
