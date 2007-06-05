#!/usr/bin/env python

import os, sys

command = None
try:
    command = sys.argv[1]
except IndexError:
    pass

os.system("intltool-extract --type=gettext/glade exaile.glade")
os.system("intltool-extract --type=gettext/glade plugins/plugins.glade")
os.system("xgettext -k_ -kN_ -o messages.pot *.py plugins/*.py xl/media/*.py xl/*.py exaile.glade.h plugins/plugins.glade.h")

if command != 'compile':
    print "\n\n**********\n"
    print "Now edit messages.pot, save it as <locale>.po, and post it on\n" \
        "our ticket tracker (http://www.exaile.org/newtranslation)\n" \
        "as a new translation.\n\nThank you!"

else:
    os.chdir('po')

    files = os.listdir('.')
    for f in files:
        if f.endswith('.po'):
            d = f.replace('.po', '')
            if not os.path.isdir(d):
                os.mkdir(d, 0777)
            if not os.path.isdir('%s/LC_MESSAGES' % d):
                os.mkdir('%s/LC_MESSAGES' % d, 0777)

            os.system('msgmerge -U %s ../messages.pot' % f)
            os.system('msgfmt %s -o %s/LC_MESSAGES/exaile.mo' % (f, d))

    os.chdir('..')
