#!/usr/bin/env python

# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

__version__ = '0.2.11b'
import sys

if sys.platform == 'linux2':
    # Set process name.  Only works on Linux >= 2.1.57.
    try:
        import dl
        libc = dl.open('/lib/libc.so.6')
        libc.call('prctl', 15, 'exaile\0', 0, 0, 0) # 15 is PR_SET_NAME
    except:
        pass

import gobject
gobject.threads_init()

# this stuff is done first so that only the modules required to connect to an
# already loaded exaile (if available) are loaded.  This helps with the speed
# of remote commands, like --next, --prev
import xl.dbusinterface
EXAILE_OPTIONS = xl.dbusinterface.get_options()
DBUS_EXIT = xl.dbusinterface.test(EXAILE_OPTIONS)

# find out if they are asking for help
HELP = False
for val in sys.argv:
    if val == '-h' or val == '--help': HELP = True

if '-h' in sys.argv: sys.argv.remove('-h')
if '--help' in sys.argv: sys.argv.remove('--help')
if '--version' in sys.argv:
    print "Exaile version: %s" % __version__
    sys.exit(0)

import os.path

import pygtk
pygtk.require('2.0') # Must be before 'import gtk'
import gtk


# Find out the location of exaile's working directory, and insert it to sys.path
basedir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(os.path.join(basedir, "exaile.py")):
    if os.path.exists(os.path.join(os.getcwd(), "exaile.py")):
        basedir = os.getcwd()
sys.path.insert(0, basedir)

# Evil heuristic to check whether Exaile is installed, by looking for Makefile.
installed = not os.path.exists(os.path.join(basedir, 'Makefile'))

import xl.path
xl.path.init(basedir, installed)


# set up gettext for translations
import gettext, locale
import gtk.glade
locale.setlocale(locale.LC_ALL, '')
gettext.textdomain('exaile')
gtk.glade.textdomain('exaile')
gettext.bindtextdomain('exaile', xl.path.localedir)
gtk.glade.bindtextdomain('exaile', xl.path.localedir)

from xl import common
gtk.window_set_default_icon_from_file(xl.path.get_data('images', 'icon.png'))

from xl.gui import main as exailemain
from xl import xlmisc

import urllib
# set the user agent
urllib.URLopener.version = "Exaile/%s (compatible; Python-urllib)" % \
    __version__ 

def check_dirs():
    """
        Makes sure the required directories have been created
    """
    covers = xl.path.get_config("covers")
    if not os.path.isdir(covers):
        os.mkdir(covers)

def main(): 
    """
        Everything dispatches from this main function
    """
    p = EXAILE_OPTIONS

    if HELP:
        p.print_help()
        sys.exit(0)

    options, args = p.parse_args()
    if options.settings:
        xl.path.set_configdir(options.settings)
    elif options.dups:
        xlmisc.log("Searching for duplicates in: %s" % options.dups)
        track.find_and_delete_dups(options.dups)
        sys.exit(0)

    running_checks = ('next', 'prev', 'stop', 'play', 'guiquery', 'get_title',
        'get_artist', 'get_album', 'get_length', 'current_position',
        'inc_vol', 'dec_vol', 'query')


    # check passed arguments for options that require exaile to currently be
    # running
    if not DBUS_EXIT:
        for check in running_checks:
            if getattr(options, check):
                print "No running Exaile instance found."
                sys.exit(1)

        check_dirs()
        
        exaile = exailemain.ExaileWindow(options, xl.path.firstrun)
    else:
        sys.exit(0)

    gtk.main()

if __name__ == "__main__": 
    try:
        main()
    except SystemExit:
        raise
    except: # BaseException doesn't exist in python2.4
        import traceback
        traceback.print_exc()
        xlmisc.log_exception()
