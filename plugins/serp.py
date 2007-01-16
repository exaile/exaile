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

import plugins, time, os, gtk, subprocess, xl.media
from xl import common

PLUGIN_NAME = "Serpentine Plugin"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = "Opens the songs in the current playlist for burning in" \
    " Serpentine"
PLUGIN_ENABLED = False
w = gtk.Button()
PLUGIN_ICON = w.render_icon('gtk-cdrom', gtk.ICON_SIZE_MENU)
w.destroy()

APP = None
BUTTON = None
MENU_ITEM = None
TIPS = gtk.Tooltips()

def launch_serpentine(button, songs=None):
    """
        Launches serpentine with the specified songs as options.  If no songs
        are specified, it gets all of the songs in the currently selected
        playlist
    """
    if not songs:
        tracks = APP.tracks
        if not tracks: return
        songs = tracks.songs

    if songs:
        ar = [song.loc for song in songs if not song.type == 'stream']
        if not ar: return
        args = ['serpentine', '-o']
        args.extend(ar)
        subprocess.Popen(args, stdout=-1,
            stderr=-1)

def burn_selected(widget, event):
    """
        Launches serpentine with the selected tracks as options
    """
    tracks = APP.tracks
    if not tracks: return
    launch_serpentine(None, tracks.get_selected_tracks())

def initialize():
    """
        Adds the "burn" button to the ratings toolbar (top right), and adds
        the menu item for burning the selected tracks to the plugins context
        menu
    """
    global APP, BUTTON, MENU_ITEM
    try:
        ret = subprocess.call(['serpentine', '-h'], stdout=-1, stderr=-1)
    except OSError:
        raise plugins.PluginInitException("Serpentine was not found in your $PATH. "
            "Disabling the serpentine plugin.")
        return False

    BUTTON = gtk.Button()
    TIPS.set_tip(BUTTON, "Burn current playlist with Serpentine")
    image = gtk.Image()
    image.set_from_stock('gtk-cdrom', gtk.ICON_SIZE_BUTTON)
    BUTTON.set_image(image)
    BUTTON.set_size_request(32, 32)
    BUTTON.connect('clicked', launch_serpentine)

    APP.xml.get_widget('rating_toolbar').pack_start(BUTTON)
    BUTTON.show()

    menu = APP.plugins_menu
    MENU_ITEM = menu.append("Burn Selected", burn_selected, 'gtk-cdrom')
        
    return True

def destroy():
    """
        Removes the context menu, and removes the button from the ratings
        toolbar
    """
    global BUTTON, MENU_ITEM
    if not BUTTON: return
    
    menu = APP.plugins_menu
    if MENU_ITEM and MENU_ITEM in menu:
        menu.remove(MENU_ITEM)
    MENU_ITEM = None
    APP.xml.get_widget('rating_toolbar').remove(BUTTON)
    BUTTON.hide()
    BUTTON.destroy()
    BUTTON = None

