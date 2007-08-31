# Bluetooth plugin for Exaile
# Copyright (C) 2007 Johannes Sasongko
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from gettext import gettext as _
import subprocess
import gtk
from xl import common, xlmisc

PLUGIN_NAME = "Send via Bluetooth"
PLUGIN_VERSION = '0.2'
PLUGIN_AUTHORS = ["Johannes Sasongko <sasongko@gmail.com>"]
PLUGIN_DESCRIPTION = r"""Allows sending files via Bluetooth.\n\nRequires
gnome-obex-send."""

PLUGIN_ICON = None
PLUGIN_ENABLED = False

def send(files):
    try:
        subprocess.call(['gnome-obex-send'] + files)
    except:
        xlmisc.log_exception()

@common.threaded
def send_threaded(files):
    send(files)

def send_selected(*args):
    tracks = APP.tracks
    if not tracks: return
    selected = tracks.get_selected_tracks() or tracks.songs
    if selected:
        send_threaded([t.io_loc for t in selected if t.type != 'stream'])

MENU_ITEM = None

def initialize():
    global MENU_ITEM
    MENU_ITEM = gtk.MenuItem(_("Send via Bluetooth"))
    MENU_ITEM.connect('activate', send_selected)
    APP.xml.get_widget('tools_menu').get_submenu().append(MENU_ITEM)
    MENU_ITEM.show()
    return True

def destroy():
    global MENU_ITEM
    MENU_ITEM.destroy()
    MENU_ITEM = None
