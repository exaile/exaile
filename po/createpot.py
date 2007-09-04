#!/usr/bin/env python

import os, sys, glob

command = None
try:
    command = sys.argv[1]
except IndexError:
    pass

os.system("intltool-extract --type=gettext/glade exaile.glade")
os.system("intltool-extract --type=gettext/glade xl/plugins/plugins.glade")
os.system("intltool-extract --type=gettext/glade plugins/daap-share/gui.glade")
os.system("intltool-extract --type=gettext/glade plugins/didyouknow/gui.glade")
os.system("xgettext -o messages.pot --from-code=utf-8 -k_ -kN_ "
    "--add-comments=TRANSLATORS "
    "--copyright-holder='Adam Olsen <arolsen@gmail.com>' "
    "--msgid-bugs-address='https://bugs.launchpad.net/exaile/' "
    "*.py `find plugins -name '*.py'` `find xl -name '*.py'` "
    "exaile.glade.h xl/plugins/plugins.glade.h "
    "plugins/daap-share/gui.glade.h plugins/didyouknow/gui.glade.h")

if command != 'compile':
    print "\n\n**********\n"
    print "Now edit messages.pot, save it as <locale>.po, and post it on\n" \
        "our but tracker (https://bugs.launchpad.net/exaile/)\n\n" \
        "Thank you!"

else:
    os.chdir('po')

    files = glob.glob('*.po')
    for f in files:
        l = os.path.splitext(f)
        os.system('mkdir -p -m 0777 %s/LC_MESSAGES' % l[0])

        print "Generating translation for %s locale" % l[0]
        os.system('msgmerge -o - %s ../messages.pot | msgfmt -c -o %s/LC_MESSAGES/exaile.mo -' % (f, l[0]))

    os.chdir('..')
