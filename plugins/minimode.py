#!/usr/bin/env python
# Copyright (C) 2006 Adam Olsen <arolsen@gmail.com>
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

import gtk, gobject, pango
from xl import xlmisc
import xl.plugins as plugins

PLUGIN_NAME = "Mini Mode"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.4.4'
PLUGIN_DESCRIPTION = r"""Super groovy mini mode window!\n\nMini Mode is activated
by pressing CTRL+ALT+M\n\nYou can move the window in most cases by
ALT+drag"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None
MENU_ITEM = None
ACCEL_GROUP = None
MM_ACTIVE = False

CONS = plugins.SignalContainer()

def toggle_minimode(*e):
    """
        Toggles Minimode
    """
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

def configure():
    """
        Configuration for mini mode
    """
    exaile = APP
    settings = exaile.settings

    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    box = dialog.main

    on_top = settings.get_boolean('on_top', plugin=plugins.name(__file__), default=False)
    no_taskbar = settings.get_boolean('no_taskbar',
        plugin=plugins.name(__file__), default=False)
    decoration = settings.get_boolean('decoration',
        plugin=plugins.name(__file__), default=False)

    on_top_box = gtk.CheckButton('Always on top')
    no_taskbar_box = gtk.CheckButton('Skip taskbar')
    decoration_box = gtk.CheckButton('Window decoration')

    on_top_box.set_active(on_top)
    no_taskbar_box.set_active(no_taskbar)
    decoration_box.set_active(decoration)

    box.pack_start(on_top_box)
    box.pack_start(no_taskbar_box)
    box.pack_start(decoration_box)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()

    settings.set_boolean('on_top', on_top_box.get_active(), plugin=plugins.name(__file__))
    settings.set_boolean('no_taskbar', no_taskbar_box.get_active(), plugin=plugins.name(__file__))
    settings.set_boolean('decoration', decoration_box.get_active(), plugin=plugins.name(__file__))

class MiniWindow(gtk.Window):
    """
        The main minimode window
    """
    def __init__(self):
        """
            Initializes the minimode window
        """
        gtk.Window.__init__(self)

        self.set_title("Exaile")
        self.set_icon(APP.window.get_icon())
        self.tips = gtk.Tooltips()
        self.seek_id = None
        self.seeking = False

        main = gtk.VBox()
        main.set_border_width(3)
        self.tlabel = gtk.Label("")
        self.tlabel.set_size_request(120, 10)
        self.tlabel.set_alignment(0.0, 0.5)

        bbox = gtk.HBox()
        bbox.set_spacing(3)

        prev = self.create_button('gtk-media-previous', self.on_prev,
            'Previous')
        bbox.pack_start(prev, False)

        self.play = self.create_button('gtk-media-play', self.on_play,
            'Play/Pause')
        bbox.pack_start(self.play, False)

        self.next = self.create_button('gtk-media-next', self.on_next, 'Next')
        bbox.pack_start(self.next)

        self.model = gtk.ListStore(str, object)
        self.title_box = gtk.ComboBox(self.model)
        cell = gtk.CellRendererText()
        cell.set_property('font-desc', pango.FontDescription('Normal 8'))
        cell.set_property('ellipsize', pango.ELLIPSIZE_END)
    
        self.title_box.pack_start(cell, True)
        self.title_box.set_size_request(170, 26)
        self.title_box.add_attribute(cell, 'text', 0)
        self.title_id = \
            self.title_box.connect('changed', self.change_track)
        bbox.pack_start(self.title_box, False)

        self.seeker = gtk.HScale(gtk.Adjustment(0, 0, 100, 1, 5, 0))
        self.seeker.set_draw_value(False)
        self.seeker.set_size_request(150, -1)
        self.seeker_id = self.seeker.connect('change-value', self.seek)
        bbox.pack_start(self.seeker, False)

        self.pos_label = gtk.Label("0:00")
        self.pos_label.set_size_request(40, -1)
        self.pos_label.set_alignment(0.0, .5)
        bbox.pack_start(self.pos_label)

        mm = self.create_button('gtk-fullscreen', toggle_minimode, 'Restore'
            ' Regular View')
        bbox.pack_start(mm, False)

        main.pack_start(bbox)

        self.add(main)

        self.connect('configure-event', self.on_move)
        self.first = False

    def seek(self, range, scroll, value): 
        """
            Seeks in the current track
        """

        if self.seek_id:
            gobject.source_remove(self.seek_id)
            self.seeking = False
            self.seek_id = None

        self.seek_id = gobject.timeout_add(250, self._seek_cb, range)
        self.seeking = True

    def _seek_cb(self, range):

        duration = APP.player.current.duration
        real = long(range.get_value() * duration / 100)
        APP.player.seek(real)
        APP.player.current.submitted = True
        APP.emit('seek', real)
        self.seeking = False

    def change_track(self, combo):
        """
            Called when the user uses the title combo to pick a new song
        """
        iter = self.title_box.get_active_iter()
        if iter:
            song = self.model.get_value(iter, 1)
            APP.stop()
            APP.player.play_track(song)

    def setup_title_box(self):
        """
            Populates the title box and selects the currently playing track

            The combobox will be populated with all the tracks in the current
            playlist, UNLESS there are more than 50 songs in the playlist.  In
            that case, only the current song and the next 50 upcoming tracks
            are displayed.
        """
        blank = gtk.ListStore(str, object)
        self.title_box.set_model(blank)
        self.model.clear()
        count = 0; select = -1
        current = APP.player.current
        if current:
            select = 0
        elif APP.songs:
            select = -1
            current = APP.songs[0] 

        # if there are more than 50 songs in the current playlist, then only
        # display the next 50 tracks
        if len(APP.songs) > 50:
            if current:  
                count += 1
                self.model.append([current.title, current])

            next = current

            while True:
                next = APP.tracks.get_next_track(next)
                if not next: break
                self.model.append([next.title, next])
                count += 1
                if count >= 50: break

        # otherwise, display all songs in the current playlist
        else:
            for song in APP.songs:
                if song == current and APP.player.current:
                    select = count
                self.model.append([song.title, song])
                count += 1

        self.title_box.set_model(self.model)
        self.title_box.disconnect(self.title_id)
        if select > -1: self.title_box.set_active(select)
        self.title_id = self.title_box.connect('changed',
            self.change_track)
        self.title_box.set_sensitive(len(self.model) > 0)

    def on_move(self, *e):
        """
            Saves the position of the minimode window if it is moved
        """
        (x, y) = self.get_position()
        settings = APP.settings
        settings.set_int('x', x, plugin=plugins.name(__file__))
        settings.set_int('y', y, plugin=plugins.name(__file__))

    def show_window(self):
        """
            Gets the last position from the settings, and then
            displays the mimimode window
        """

        if not self.first:
            self.first = True
            self.show_all()
        else:
            self.show()

        settings = APP.settings
        x = settings.get_int("x", plugin=plugins.name(__file__),   
            default=10)
        y = settings.get_int("y", plugin=plugins.name(__file__),
            default=10)
        self.move(x, y)
        self.setup_title_box()
        self.stick()

        if APP.settings.get_boolean('on_top', plugin=plugins.name(__file__),
            default=False):
            self.set_keep_above(True)
        else:
            self.set_keep_above(False)

        if APP.settings.get_boolean('no_taskbar',
            plugin=plugins.name(__file__), default=False):
            self.set_property('skip-taskbar-hint', True)
        else:
            self.set_property('skip-taskbar-hint', False)

        if APP.settings.get_boolean('decoration',
            plugin=plugins.name(__file__), default=False):
            self.set_decorated(True)
        else:
            self.set_decorated(False)

    def on_prev(self, button):
        """
            Called when the user presses the previous button
        """

        APP.player.previous()
        self.timeout_cb()

    def on_play(self, button):
        """
            Called when the user clicks the play button
        """

        APP.player.toggle_pause()
        self.timeout_cb()

    def on_stop(self, button=None):
        """
            Called when the user clicks the stop button
        """

        if button: APP.player.stop(True)
        self.timeout_cb()
        self.play.set_image(APP.get_play_image(gtk.ICON_SIZE_MENU))
        self.setup_title_box()
        self.set_title(APP.window.get_title())

    def on_next(self, button):
        """ 
            Called when the user clicks the next button
        """
        
        APP.player.next()
        self.timeout_cb()

    def create_button(self, stock_id, func, tip):
        """
            Creates a little button
        """
        button = gtk.Button()
        button.connect('clicked', func)
        image = gtk.Image()
        image.set_from_stock(stock_id, gtk.ICON_SIZE_MENU)
        button.set_image(image)
        button.set_size_request(26, 26)
        self.tips.set_tip(button, tip)

        return button

    def pause_toggled(self):
        """
            Called when pause is toggled
        """

        track = APP.player.current
        if not track:
            self.play.set_image(APP.get_play_image(gtk.ICON_SIZE_MENU))
        else:
            if APP.player.is_paused():
                self.play.set_image(APP.get_play_image(gtk.ICON_SIZE_MENU))
            else:
                self.play.set_image(APP.get_pause_image(gtk.ICON_SIZE_MENU))
        self.set_title(APP.window.get_title())

    def timeout_cb(self):
        text = APP.new_progressbar.get_text()
        b = text.find(' /')
        if b > -1:
            text = text[:b]
        self.pos_label.set_label(text)
        self.seeker.set_value(APP.new_progressbar.get_fraction() * 100)
            
        return True

def pause_toggled(exaile, track):
    PLUGIN.pause_toggled()

def play_track(exaile, track):
    PLUGIN.pause_toggled()
    PLUGIN.setup_title_box()

def stop_track(exaile, track):
    PLUGIN.on_stop()

def toggle_hide(*args):
    if not MM_ACTIVE: return False

    if PLUGIN.get_property("visible"):
        PLUGIN.hide()
    else: PLUGIN.show_window()

    return True

def tray_toggled(app, enabled):
    if enabled:
        CONS.connect(app.tray_icon, 'toggle-hide', toggle_hide)
    else:
        CONS.disconnect_object(app.tray_icon)

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
    CONS.connect(APP.player, 'play-track', play_track)
    CONS.connect(APP.player, 'stop-track', stop_track)
    CONS.connect(APP.player, 'pause-toggled', pause_toggled)

    if APP.tray_icon:
        CONS.connect(APP.tray_icon, 'toggle-hide', toggle_hide)
    CONS.connect(APP, 'tray-icon-toggled', tray_toggled)
    return True

def destroy():
    global PLUGIN, MENU_ITEM, ACCEL_GROUP, MENU_ITEM, TIMER_ID

    CONS.disconnect_all()

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
