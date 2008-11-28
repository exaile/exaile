#!/usr/bin/env python

import os, sys, glob

command = None
try:
    command = sys.argv[1]
except IndexError:
    pass

os.chdir('po')
os.system('intltool-update --pot --gettext-package=messages --verbose')

if command != 'compile':
    print "\n\n**********\n"
    print "Now edit messages.pot, save it as <locale>.po, and post it on\n" \
        "our bug tracker (https://bugs.launchpad.net/exaile/)\n\n" \
        "Thank you!"

else:

    files = glob.glob('*.po')
    for f in files:
        l = os.path.splitext(f)
        os.system('mkdir -p -m 0777 %s/LC_MESSAGES' % l[0])

        print "Generating translation for %s locale" % l[0]
        os.system('msgmerge -o - %s messages.pot | msgfmt -c -o %s/LC_MESSAGES/exaile.mo -' % (f, l[0]))

os.chdir('..')
