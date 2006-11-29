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

PLUGIN_NAME = "Desktop Cover"
PLUGIN_AUTHORS = ["Johannes Sasongko <sasongko@gmail.com>", 
    "Adam Olsen <arolsen@gmail.com>"]

PLUGIN_VERSION = "0.1"
PLUGIN_DESCRIPTION = "Displays the current album cover on the desktop"
PLUGIN_ENABLED = False
PLUGIN_ICON = None

import gtk, re, gobject, xl.common
import plugins, gobject

PLUGIN = None
CON = plugins.SignalContainer()

class CoverDisplay(gtk.Window):
    def __init__(self, exaile, geometry=''):
        gtk.Window.__init__(self)
        self.exaile = exaile
        self.geometry = geometry
        self.first = False
        self.init_gtk(False)
        self.img = gtk.Image()
        self.add(self.img)
    
    def init_gtk(self, show=True):

        self.stick()
        
        self.parse_geometry()

        if show:
            if not self.first:
                self.first = True
                self.show_all()
            else:
                self.deiconify()
        self.set_accept_focus(False)
        self.set_decorated(False)
        self.set_keep_below(True)
        self.set_resizable(False)
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)

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
            print "No x and y"
            self.set_position(gtk.WIN_POS_CENTER_ALWAYS)
    
    def play_track(self, exaile=None, track=None):
        """
            Called by the plugin chain when a new track starts playing
        """
        newcover = self.exaile.cover.loc
        
        if newcover.find('nocover') == -1:
            self.display(newcover)
        else:
            self.display(None)
        return True

    def stop_track(self, exaile, track):
        """
            Called when playing of a track stops
        """
        self.display(None)
    
    def display(self, cover):
        if cover == None:
            self.img.clear()
            self.iconify()
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
    
        self.init_gtk()

def configure():
    """
        Called when a configure request is called
    """
    global PLUGIN
    exaile = APP
    settings = exaile.settings
    geometry = settings.get('%s_geometry' % plugins.name(__file__), '150x150')

    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    box = dialog.main
    table = gtk.Table(4, 2)
    table.set_row_spacings(2)
    table.set_col_spacings(2)

    match = re.match(
            '^=?(?:(\d+)?(?:[Xx](\d+))?)?'
            '(?:([+-])(\d+)?(?:([+-])(\d+))?)?$',
            geometry)
    if not match:
        w, h, px, x, py, y = '150', '150', '+', '0', '+', '0'
    else:
        w, h, px, x, py, y = match.groups()

    if not w: w = '150'
    if not h: h = '150'
    if not px or px == '+': px = ''
    if not py or py == '+': py = ''
    if x == '' or x is None: x = ''
    if y == '' or y is None: y = ''

    y = "%s%s" % (py, y)
    x = "%s%s" % (px, x)
    boxes = dict()
    items = ('Width:w', 'Height:h', 'X:x', 'Y:y')
    bottom = 0
    for item in items:
        (name, prop) = item.split(':')
        label = gtk.Label("%s:    " % name)
        label.set_alignment(0, 0)

        table.attach(label, 0, 1, bottom, bottom + 1,
            gtk.EXPAND|gtk.FILL, gtk.FILL)
        field = gtk.Entry()
        field.set_text(locals()[prop])
        field.set_max_length(5)
        table.attach(field, 1, 2, bottom, bottom + 1,
            gtk.EXPAND|gtk.FILL, gtk.FILL)
        boxes[prop] = field
        bottom += 1

    box.pack_start(table, False, False)
    box.pack_start(gtk.Label("Leave X and Y empty to center"),
        False, False)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:
        new = dict()
        for item in items:
            (name, item) = item.split(':')
            val = boxes[item].get_text()
            if val:
                try:    
                    int(val)
                except ValueError:
                    xl.common.error(exaile.window, _("Invalid "
                        "setting for %s" % item.upper()))
                    return

            new[item] = val

        for item in ('x', 'y'):
            if new[item] and new[item].find("-") <= -1:
                new[item] = "+%s" % new[item]

        settings["%s_geometry" % plugins.name(__file__)] = \
            "%sx%s%s%s" % (new['w'], new['h'], new['x'], new['y'])
        geometry = settings["%s_geometry" % plugins.name(__file__)] = \
            "%sx%s%s%s" % (new['w'], new['h'], new['x'], new['y'])
        if PLUGIN:
            PLUGIN.destroy()
            PLUGIN = CoverDisplay(exaile, geometry)
        track = exaile.current_track

        if not track: return
        if track and track.is_playing() or track.is_paused():
            if PLUGIN: PLUGIN.play_track(track)
        print "New settings: %s" % settings["%s_geometry" %
            plugins.name(__file__)]

def play_track(exaile, track):
    """
        Called when a track starts playing
    """
    if PLUGIN:
        PLUGIN.play_track(track)

def stop_track(exaile, track):
    """
        Called when a track stops playing
    """
    if PLUGIN:
        PLUGIN.stop_track(track)

def initialize():
    """
        Inizializes the plugin
    """
    global PLUGIN, SETTINGS, APP
    exaile = APP
    SETTINGS = exaile.settings
    print "%s_geometry" % \
        plugins.name(__file__)

    geometry = exaile.settings.get("%s_geometry" % 
        plugins.name(__file__), "150x150")
    print "Cover geometry: %s" % geometry
    PLUGIN = CoverDisplay(exaile, geometry)

    CON.connect(APP, 'play-track', PLUGIN.play_track)
    CON.connect(APP, 'stop-track', PLUGIN.stop_track)
    CON.connect(APP.cover, 'image-changed', PLUGIN.play_track)

    return True

def destroy():
    """
        Destroys the plugin
    """
    global PLUGIN, PLAY_ID, STOP_ID, COVER_ID

    CON.disconnect_all()

    if PLUGIN:
        PLUGIN.destroy()


    PLUGIN = None
