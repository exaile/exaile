# Copyright (C) 2007 Aren Olson
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

import dbus, time, gtk
from gettext import gettext as _
import xl.plugins as plugins
from xl import common

PLUGIN_NAME = _("AWN")
PLUGIN_AUTHORS = ['Aren Olson <reacocard@gmail.com>', 'Bryan Forbes <bryan@reigndropsfall.net>', 'Alberto Pagliarini <batopa@gmail.com>']
PLUGIN_VERSION = '0.7.4'
PLUGIN_DESCRIPTION = _(r"""Displays the current album's cover art, progress and/or remaining time in AWN.""")

PLUGIN_ENABLED = False
PLUGIN_ICON = None

SHOW_PROGRESS = False
SHOW_TIMER = False
SHOW_COVER = True

UPDATER = None
CONS = plugins.SignalContainer()

class updater:
    def __init__(self):
        """
            Set everything up.
        """
        #self.setup_awn()
        self.cover = None
        self.cover_update = 0
        self.updating = False
        self.connected = False
        self.do_update = 0

    def update_cover(self, widget=None, args=None):
        self.cover_update = 3

    def run_update(self, widget=None, args=None):
        """
            Run the updater, if necessary.
        """
        #progressbar sends two events/sec, so only update 1/2 the time.
        if self.do_update:
            self.update()
            self.do_update = 0
        else:
            self.do_update = 1

    @common.threaded
    def update(self):
        """
            Update cover, progress, time.
        """
        if not self.connected:
            self.setup_awn()
        if not self.updating:
            self.updating = True
            try:
                #Set album cover
                newcover = APP.cover.loc
                if SHOW_COVER and self.cover_update:
                    if 'nocover' in newcover:
                        self.awn.UnsetTaskIconByName(APP.window.get_title())
                        self.cover = None
                    else:
                        self.awn.SetTaskIconByName(APP.window.get_title(), newcover)
                        self.cover = newcover
                    self.cover_update = self.cover_update - 1

                #Update progress meter.
                if SHOW_PROGRESS:
                    if APP.player.is_playing():
                        position = int(round(APP.player.get_current_position(),0))
                        self.awn.SetProgressByName(APP.window.get_title(), position)
                    else:
                        self.awn.SetProgressByName(APP.window.get_title(), 100)
                else:
                    self.awn.SetProgressByName(APP.window.get_title(), 100)

                #Update remaining time.
                if SHOW_TIMER:
                    if APP.player.is_playing() or APP.player.is_paused():
                        time_remaining = APP.new_progressbar.get_text().split('/ ')[1]
                        self.awn.SetInfoByName(APP.window.get_title(), time_remaining)
                    else:
                        self.awn.UnsetInfoByName(APP.window.get_title())
                else:
                    self.awn.UnsetInfoByName(APP.window.get_title())

            except:
                self.connected = False
            self.updating = False

    def setup_awn(self):
        try:
            bus_obj = dbus.SessionBus().get_object("com.google.code.Awn",
                "/com/google/code/Awn")
            self.awn = dbus.Interface(bus_obj, "com.google.code.Awn")
            self.connected = True
        except:
            self.connected = False
            self.awn = None

def configure():
    """
        Show a configuration dialog.
    """
    global SHOW_PROGRESS, SHOW_TIMER
    dialog = plugins.PluginConfigDialog(APP.window, PLUGIN_NAME)

    box = dialog.main

    show_timer_box = gtk.RadioButton(label=_("Show song's remaining time in AWN"))
    show_timer_box.set_active(SHOW_TIMER)

    show_progress_box = gtk.RadioButton(group=show_timer_box,
        label=_("Show song's progress in AWN"))
    show_progress_box.set_active(SHOW_PROGRESS)

    do_nothing_box = gtk.RadioButton(group=show_timer_box,
        label=_("Don't show any extra information"))
    if not SHOW_PROGRESS and not SHOW_TIMER:
        do_nothing_box.set_active(True)

    box.pack_start(show_progress_box)
    box.pack_start(show_timer_box)
    box.pack_start(do_nothing_box)
    dialog.show_all()
    result = dialog.run()
    dialog.hide()

    APP.settings.set_boolean('show_progress', show_progress_box.get_active(),
        plugin=plugins.name(__file__))
    APP.settings.set_boolean('show_timer', show_timer_box.get_active(),
        plugin=plugins.name(__file__))

    SHOW_PROGRESS = APP.settings.get_boolean('show_progress',
        plugin=plugins.name(__file__), default=False)
    SHOW_TIMER = APP.settings.get_boolean('show_timer',
        plugin=plugins.name(__file__), default=False)

def initialize():
    """
        Set up the updater.
    """
    global SHOW_PROGRESS, SHOW_TIMER, UPDATER

    SHOW_PROGRESS = APP.settings.get_boolean('show_progress',
        plugin=plugins.name(__file__), default=False)

    SHOW_TIMER = APP.settings.get_boolean('show_timer',
        plugin=plugins.name(__file__), default=False)

    UPDATER = updater()

    #update whenever something changes
    CONS.connect(APP.new_progressbar, 'notify', UPDATER.run_update)
    CONS.connect(APP.cover, 'image-changed', UPDATER.update_cover)
    try:
        CONS.connect(APP.tray_icon, 'toggle-hide', UPDATER.update_cover)
    except:
        pass

    UPDATER.update_cover()

    return True

def destroy():
    """
        Disconnect from AWN.
    """
    global UPDATER
    
    CONS.disconnect_all()
    try:
        UPDATER.awn.UnsetTaskIconByName(APP.window.get_title())
        UPDATER.awn.SetProgressByName(APP.window.get_title(), 100)
        UPDATER.awn.UnsetInfoByName(APP.window.get_title())
    except:
        pass
    UPDATER.awn = None
    UPDATER = None
    
