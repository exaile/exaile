#!/usr/bin/env python

import os, sys, glob

command = None
try:
    command = sys.argv[1]
except IndexError:
    pass

os.system("xgettext -c -k_ -kN_ -o messages.pot "
    "*.py plugins/*.py `find xl -name '*.py'` "
    "exaile.glade plugins/plugins.glade")

if command != 'compile':
    print "Now edit messages.pot, save it as <locale>.po, and post it on\n" \
        "our ticket tracker (http://www.exaile.org/newtranslation)\n" \
        "as a new translation.\n\nThank you!"

else:
    os.chdir('po')

    files = glob.glob('*.po')
    for f in files:
        l = os.path.splitext(f)
        os.system('mkdir -p -m 0777 %s/LC_MESSAGES' % l[0])

        print "Generating translation for %s locale" % l[0]
        os.system('msgmerge -o - %s ../messages.pot | msgfmt -c -o %s/LC_MESSAGES/exaile.mo -' % (f, l[0]))

    os.chdir('..')
