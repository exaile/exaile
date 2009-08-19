#!/usr/bin/env python
# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os, sys, glob

command = None
try:
    command = sys.argv[1]
except IndexError:
    pass

os.environ['XGETTEXT_ARGS'] = '--language=Python'
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
