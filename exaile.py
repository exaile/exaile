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

__version__ = '0.2.14devel'

import sys

if sys.platform == 'linux2':
    # Set process name.  Only works on Linux >= 2.1.57.
    try:
        import ctypes
        libc = ctypes.CDLL('libc.so.6')
        libc.prctl(15, 'exaile\0')
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

# find out if they are asking for help or version
HELP = False
for val in sys.argv[:]:
    if val in ('-h', '--help'):
        HELP = True
        sys.argv.remove(val)
    elif val == '--version':
        print "Exaile version:", __version__
        sys.exit(0)

import os.path

import pygtk
pygtk.require('2.0') # Must be before 'import gtk'
import gtk


# Find out the location of exaile's working directory, and insert it to sys.path
basedir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(os.path.join(basedir, "exaile.py")):
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "exaile.py")):
        basedir = cwd
sys.path.insert(0, basedir)

# Evil heuristic to check whether Exaile is installed, by looking for Makefile.
installed = not os.path.exists(os.path.join(basedir, 'Makefile'))

import xl.path

options, args = EXAILE_OPTIONS.parse_args()
if options.settings: 
    xl.path.set_configdir(options.settings)
xl.path.init(basedir, installed)


# set up gettext for translations
import gettext, locale
import gtk.glade
locale.setlocale(locale.LC_ALL, None)
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

def init():
    global exaile
    if HELP:
        EXAILE_OPTIONS.print_help()
        sys.exit(0)

    if DBUS_EXIT:
        sys.exit(0)

    running_checks = ('next', 'prev', 'stop', 'play', 'guiquery', 'get_title',
        'get_artist', 'get_album', 'get_length', 'current_position',
        'inc_vol', 'dec_vol', 'get_volume', 'query')

    # check passed arguments for options that require exaile to currently be
    # running
    for check in running_checks:
        if getattr(options, check):
            print "No running Exaile instance found."
            sys.exit(1)

    check_dirs()

    xlmisc.log("Exaile " + __version__)
    exaile = exailemain.ExaileWindow(options, xl.path.firstrun)

if __name__ == "__main__": 
    try:
        init()
        gtk.main()
    except SystemExit:
        raise
    except Exception:
        xlmisc.log_exception()
