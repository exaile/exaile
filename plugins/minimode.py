#!/usr/bin/env python
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

import gtk, plugins, gobject

PLUGIN_NAME = "Mini Mode"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r"""Allows for a mini mode window.\nMini Mode is activated
by pressing CTRL+ALT+M"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None
MENU_ITEM = None
ACCEL_GROUP = None
TIMER_ID = None
MM_ACTIVE = False

class MiniWindow(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)

        self.set_title("Exaile!")
        self.set_icon(APP.window.get_icon())

        main = gtk.VBox()
        main.set_spacing(2)
        main.set_border_width(2)

        self.title_label = gtk.Label()
        self.title_label.set_markup("<b>Now Playing</b>")
        self.title_label.set_alignment(0.0, 0.0)
        main.pack_start(self.title_label)
        artist_box = gtk.HBox()

        self.artist_label = gtk.Label("Artist")
        self.artist_label.set_alignment(0.0, 0.0)
        self.volume_label = gtk.Label("Vol: 0%")
        self.volume_label.set_alignment(1.0, 0.0)
        artist_box.pack_start(self.artist_label, True)
        artist_box.pack_end(self.volume_label, False)
        main.pack_start(artist_box)

        box = gtk.HBox()
        box.set_spacing(2)
        prev = self.create_button('gtk-media-previous', self.on_prev)
        box.pack_start(prev, False)
        self.play = self.create_button('gtk-media-play', self.on_play)

        box.pack_start(self.play, False)
        stop = self.create_button('gtk-media-stop', self.on_stop)
        box.pack_start(stop, False)
        next = self.create_button('gtk-media-next', self.on_next)
        box.pack_start(next, False)

        self.seeker = gtk.HScale(gtk.Adjustment(0, 0, 100, 1, 5, 0))
        self.seeker.set_draw_value(False)
        self.seeker.set_size_request(200, -1)
        self.seeker.connect('change-value', APP.seek)
        box.pack_start(self.seeker, True, True)
        self.pos_label = gtk.Label("0:00")
        box.pack_start(self.pos_label, False)
        main.pack_start(box)
        self.connect('delete-event', self.on_quit)
        self.connect('configure-event', self.on_move)

        self.add(main)
        self.set_resizable(False)
        self.first = False

    def on_move(self, *e):
        (x, y) = self.get_position()
        settings = APP.settings
        settings['%s_x' % plugins.name(__file__)] = x
        settings['%s_y' % plugins.name(__file__)] = y

    def on_quit(self, widget=None, event=None):
        if widget == self and APP.tray_icon:
            self.hide()
            return True
        else:
            return APP.on_quit(widget, event)

    def show_window(self):
        if not self.first:
            self.first = True
            self.show_all()
        else:
            self.show()

        settings = APP.settings
        x = settings.get_int("%s_x" % plugins.name(__file__),   
            10)
        y = settings.get_int("%s_y" % plugins.name(__file__),
            10)
        self.move(x, y)

    def on_prev(self, button):
        APP.on_previous()
        self.timeout_cb()

    def on_play(self, button):
        APP.toggle_pause()
        self.timeout_cb()

    def on_stop(self, button):
        APP.stop()
        self.timeout_cb()
        self.play.set_image(APP.get_play_image())
        self.title_label.set_markup("<b>Stopped</b>")
        self.artist_label.set_label("Stopped")

    def on_next(self, button):
        APP.on_next()
        self.timeout_cb()

    def create_button(self, stock_id, func):
        """
            Creates a little button
        """
        button = gtk.Button()
        button.connect('clicked', func)
        image = gtk.Image()
        image.set_from_stock(stock_id, gtk.ICON_SIZE_SMALL_TOOLBAR)
        button.set_image(image)

        return button

    def pause_toggled(self):
        track = APP.current_track
        if not track:
            self.play.set_image(APP.get_play_image())
        else:
            if track.is_paused():
                self.play.set_image(APP.get_play_image())
            else:
                self.play.set_image(APP.get_pause_image())

    def timeout_cb(self):
        self.seeker.set_value(APP.progress.get_value())
        self.pos_label.set_label(APP.progress_label.get_label())

        track = APP.current_track
        self.volume_label.set_label("Vol: %s%%" % APP.get_volume_percent())
        if not track:
            self.title_label.set_markup("<b>Stopped</b>")
            self.artist_label.set_label("Stopped")
        else:

            self.title_label.set_markup("<b>%s</b>" % track.title)
            self.artist_label.set_label("by %s" % track.artist)
            
        return True

def pause_toggled(track):
    PLUGIN.pause_toggled()

def play_track(track):
    PLUGIN.pause_toggled()

def toggle_minimode(*e):
    global MM_ACTIVE 
    if not PLUGIN.get_property("visible"):
        PLUGIN.show_window()
        APP.window.hide()
        MM_ACTIVE = True
    else:
        PLUGIN.hide()
        MM_ACTIVE = False
        APP.window.show()
    print "Minimode toggled"

def toggle_hide(*args):
    if not MM_ACTIVE: return True

    if PLUGIN.get_property("visible"):
        PLUGIN.hide()
    else: PLUGIN.show_window()

    return False

def pass_func(*args):
    global MM_ACTIVE 
    if PLUGIN.get_property("visible"):
        PLUGIN.hide()
        MM_ACTIVE = False
        APP.window.show()
        return True

def initialize():
    global TIMER_ID, PLUGIN, ACCEL_GROUP, MENU_ITEM

    PLUGIN = MiniWindow()
    TIMER_ID = gobject.timeout_add(1000, PLUGIN.timeout_cb)
    ACCEL_GROUP = gtk.AccelGroup()
    key, mod = gtk.accelerator_parse("<Control><Alt>M")
    ACCEL_GROUP.connect_group(key, mod, gtk.ACCEL_VISIBLE, pass_func)

    APP.window.add_accel_group(ACCEL_GROUP)
    MENU_ITEM = gtk.MenuItem("Mini Mode")
    MENU_ITEM.connect('activate', toggle_minimode)
    MENU_ITEM.add_accelerator('activate', ACCEL_GROUP, key, mod,
        gtk.ACCEL_VISIBLE)
    APP.view_menu.get_submenu().append(MENU_ITEM)
    MENU_ITEM.show()
    PLUGIN.add_accel_group(ACCEL_GROUP)
    return True

def destroy():
    global PLUGIN, MENU_ITEM, ACCEL_GROUP, MENU_ITEM

    if TIMER_ID:
        gobject.source_remove(TIMER_ID)
        TIMER_ID = None

    if PLUGIN:
        PLUGIN.destroy()
        PLUGIN = None

    if MENU_ITEM:
        APP.view_menu.get_submenu().remove(MENU_ITEM)
        MENU_ITEM = None
        
    if ACCEL_GROUP: 
        APP.window.remove_accel_group(ACCEL_GROUP)
        ACCEL_GROUP = None
