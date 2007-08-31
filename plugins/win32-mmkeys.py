# win32-mmkeys - Adds support for multimedia keys in MS Windows.
# Copyright (C) 2007 Johannes Sasongko <sasongko@gmail.com>
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

PLUGIN_NAME = "Windows multimedia keys"
PLUGIN_AUTHORS = ["Johannes Sasongko <sasongko@gmail.com>"]

PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = r"""Adds support for multimedia keys in MS Windows.
\n\nRequires pyHook, http://www.cs.unc.edu/Research/assist/developer.shtml"""
PLUGIN_ENABLED = False

import gtk
PLUGIN_ICON = gtk.Label().render_icon(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)


KEY_MAP = None # For fast key-to-function mapping.

def on_key_down(event):
    try:
        KEY_MAP[event.GetKey()]()
        return False # Swallow.
    except KeyError:
        return True


PLUGIN = None

def initialize():
    global KEY_MAP, PLUGIN

    KEY_MAP = {
        'Media_Prev_Track': APP.player.previous,
        'Media_Play_Pause': APP.player.toggle_pause,
        'Media_Stop': APP.player.stop,
        'Media_Next_Track': APP.player.next,
    }

    import pyHook
    PLUGIN = pyHook.HookManager()
    PLUGIN.KeyDown = on_key_down
    PLUGIN.HookKeyboard()

    return True

def destroy():
    global KEY_MAP, PLUGIN
    PLUGIN.UnhookKeyboard()
    KEY_MAP = PLUGIN = None
