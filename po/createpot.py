#!/usr/bin/env python

import os, sys

if len(sys.argv) <= 1:
    os.system("intltool-extract --type=gettext/glade exaile.glade")
    os.system("intltool-extract --type=gettext/glade plugins/plugins.glade")
    os.system("xgettext -k_ -kN_ -o messages.pot *.py xl/*.py exaile.glade.h plugins/plugins.glade.h")
    print "\n\n**********\n"
    print "Now edit messages.pot, save it as <locale>.po, and post it on\n" \
        "our ticket tracker (http://www.exaile.org/newtranslation)\n" \
        "as a new translation.\n\nThank you!"
