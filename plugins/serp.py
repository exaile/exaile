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

PLUGIN_NAME = "Serpentine Plugin"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = "Opens the songs in the current playlist for burning in" \
    " Serpentine"
PLUGIN_ENABLED = False
w = gtk.Button()
PLUGIN_ICON = w.render_icon('gtk-cdrom', gtk.ICON_SIZE_MENU)

EXAILE = None
BUTTON = None
TIPS = gtk.Tooltips()

def launch_serpentine(button):
    tracks = EXAILE.tracks
    if tracks:
        songs = tracks.songs
        if songs:
            ar = [song.loc for song in songs if not isinstance(song,
                xl.media.StreamTrack)]
            if not ar: return
            args = ['serpentine', '-o']
            args.extend(ar)
            subprocess.Popen(args, stdout=-1,
                stderr=-1)

def initialize(exaile):
    global EXAILE, BUTTON
    try:
        ret = subprocess.call(['serpentine', '-h'], stdout=-1, stderr=-1)
    except OSError:
        raise Exception("Serpentine was not found")
        return False

    EXAILE = exaile
    BUTTON = gtk.Button()
    TIPS.set_tip(BUTTON, "Burn current playlist with Serpentine")
    image = gtk.Image()
    image.set_from_stock('gtk-cdrom', gtk.ICON_SIZE_SMALL_TOOLBAR)
    BUTTON.set_image(image)
    BUTTON.connect('clicked', launch_serpentine)

    EXAILE.xml.get_widget('rating_toolbar').pack_start(BUTTON)
    BUTTON.show()
    return True

def destroy():
    global BUTTON
    if not BUTTON: return
    EXAILE.xml.get_widget('rating_toolbar').remove(BUTTON)
    BUTTON.hide()
    BUTTON.destroy()
    BUTTON = None

