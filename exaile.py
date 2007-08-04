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

## Find out the location of exaile's working directory, and go there
basedir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(os.path.join(basedir, "exaile.py")):
    if os.path.exists(os.path.join(os.getcwd(), "exaile.py")):
        basedir = os.getcwd()
sys.path.insert(0, basedir)
os.chdir(basedir)

# Heuristic to check whether Exaile is installed.
# Sets prefix accordingly, otherwise it is ".".
prefix = '.'
path_suffix = '%sshare%sexaile' % (os.sep, os.sep)
if basedir.endswith(path_suffix):
    prefix = basedir[:-len(path_suffix)]
    # Add ../../lib/exaile to path, otherwise Exaile won't be able to import any
    # of its modules.
    sys.path.append(os.path.join(prefix, 'lib', 'exaile'))

# set up gettext for translations
import gettext, locale
import gtk.glade
locale.setlocale(locale.LC_ALL, '')
gettext.textdomain('exaile')
gtk.glade.textdomain('exaile')
if prefix == '.': # if Exaile is not installed
    gettext.bindtextdomain('exaile', 'po')
    gtk.glade.bindtextdomain('exaile', 'po')
else:
    gtk.glade.bindtextdomain('exaile', os.path.join(prefix, 'share', 'locale'))

gtk.window_set_default_icon_from_file("images%sicon.png"% os.sep)
SETTINGS_DIR = os.path.expanduser('~/.exaile')
GCONF_DIR = "/apps/exaile"

from xl.gui import main as exailemain
from xl import xlmisc

def check_dirs():
    """
        Makes sure the required directories have been created
    """
    covers = os.path.join(SETTINGS_DIR, "covers")
    cache = os.path.join(SETTINGS_DIR, "cache")
    if not os.path.isdir(covers):
        os.mkdir(covers)

    if not os.path.isdir(cache):
        os.mkdir(cache)
    
def first_run(): 
    """
        Called if the music database or settings files are missing.

        Creates the settings directory, and, if necessary, creates the initial
        database file.

        Also scans the default import directory in case there's any music files
        there.
    """
    try:
        os.mkdir(SETTINGS_DIR)
    except:
        print "Could not create settings directory"

def main(): 
    """
        Everything dispatches from this main function
    """
    global SETTINGS_DIR
    p = EXAILE_OPTIONS

    if HELP:
        p.print_help()
        sys.exit(0)

    options, args = p.parse_args()
    if options.settings:
        SETTINGS_DIR = options.settings
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

        fr = False
        if not os.path.isdir(SETTINGS_DIR):
            first_run()
            fr = True


        check_dirs()
        
        exaile = exailemain.ExaileWindow(SETTINGS_DIR, options, fr)
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
