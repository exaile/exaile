#!/usr/bin/env python

# exailecover - displays Exaile album covers on the desktop
# Copyright (C) 2006 Johannes Sasongko <sasongko@gmail.com>
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

PLUGIN_NAME = "desktopcover"
PLUGIN_AUTHORS = ["Johannes Sasongko <sasongko@gmail.com", 
    "Adam Olsen arolsen@gmail.com"]

PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = "Displays the current album cover on the desktop"

import gtk, re, gobject
import plugins

PLUGIN = None

class CoverDisplay(gtk.Window):
    def __init__(self, exaile, geometry=''):
        self.exaile = exaile
        self.geometry = geometry
        self.init_gtk()
    
    def init_gtk(self):
        gtk.Window.__init__(self)
        self.connect('destroy', gtk.main_quit)
        self.set_accept_focus(False)
        self.set_decorated(False)
        self.set_keep_below(True)
        self.set_resizable(False)
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.stick()
        
        self.img = gtk.Image()
        self.add(self.img)
        
        self.parse_geometry()
        self.show_all()
    
    def parse_geometry(self):
        match = re.match(
                '^=?(?:(\d+)?(?:[Xx](\d+))?)?'
                '(?:([+-])(\d+)?(?:([+-])(\d+))?)?$',
                self.geometry)
        if not match:
            raise ValueError('invalid geometry: ' + self.geometry)
        w, h, px, x, py, y = match.groups()
        
        if w and h:
            self.w = int(w)
            self.h = int(h)
        else:
            self.w = None
            self.h = None
        
        if x and y:
            gtk.Window.parse_geometry(self, self.geometry)
        else:
            self.set_position(gtk.WIN_POS_CENTER_ALWAYS)
    
    def play_track(self, track):
        """
            Called by the plugin chain when a new track starts playing
        """
        newcover = self.exaile.cover.loc
        print "play track was called"
        
        print newcover
        if newcover.find('nocover') == -1:
            self.display(newcover)
        else:
            self.display(None)
        return True

    def stop_track(self, track):
        """
            Called when playing of a track stops
        """
        self.display(None)
    
    def display(self, cover):
        if cover == None:
            self.img.clear()
            return
        
        pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if self.w is not None and self.h is not None:
            origw = float(width)
            origh = float(width)
            width, height = self.w, self.h
            scale = min(width / origw, height / origh)
            width = int(origw * scale)
            height = int(origh * scale)
            pixbuf = pixbuf.scale_simple(
                    width, height, gtk.gdk.INTERP_BILINEAR)
        self.img.set_from_pixbuf(pixbuf)

def initialize(exaile):
    """
        Inizializes the plugin
    """
    global PLUGIN
    print "%s_geometry" % \
        plugins.name(__file__)
    geometry = exaile.settings.get("%s_geometry" % 
        plugins.name(__file__), "150x150")
    print "Cover geometry: %s" % geometry
    PLUGIN = CoverDisplay(exaile, geometry)

    return True

def play_track(track):
    """
        Called when a track starts playing
    """
    if PLUGIN:
        PLUGIN.play_track(track)

def stop_track(track):
    """
        Called when a track stops playing
    """
    if PLUGIN:
        PLUGIN.stop_track(track)

def destroy():
    """
        Destroys the plugin
    """
    global PLUGIN
    if PLUGIN:
        PLUGIN.destroy()

    PLUGIN = None
