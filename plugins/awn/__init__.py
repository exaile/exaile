# Copyright (C) 2009-2010 Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import urlparse
import urllib
import logging

import dbus
from gi.repository import Gtk
from gi.repository import GLib
import os
import tempfile

from xl import covers, player
import xl.event
import xl.settings

from xlgui import icons

import awn_prefs

log = logging.getLogger(__name__)


class InvalidOverlayOption(Exception):

    def __init__(self, option):
        self.option = option

    def __str__(self):
        return 'Got %s, must be one of %s' % (
            repr(self.option),
            str(awn_prefs.OverlayDisplay.map)
        )


class ExaileAwn(object):

    def __init__(self):
        bus = dbus.SessionBus()
        obj = bus.get_object("com.google.code.Awn", "/com/google/code/Awn")
        self.awn = dbus.Interface(obj, "com.google.code.Awn")
        self.exaile = None
        self.enabled = True
        self.timer_id = None
        self.temp_icon_path = None

    def enable_progress(self, type, player, object):
        assert self.timer_id is None
        GLib.timeout_add_seconds(1, self.update_timer)

    def disable_progress(self, type, player, object, clear_menu=True):
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
        self.timer_id = None
        if clear_menu:
            self._set_timer(100)

    def toggle_pause_progress(self, type, player, object):
        if self.timer_id is not None:
            self.disable_progress(type, player, object, False)
        else:
            self.enable_progress(type, player, object)

    def __inner_preference(klass):
        """Function will make a property for a given subclass of Preference"""

        def getter(self):
            return xl.settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            xl.settings.set_option(klass.name, val)

        return property(getter, setter)

    overlay = __inner_preference(awn_prefs.OverlayDisplay)
    cover_display = __inner_preference(awn_prefs.CoverDisplay)

    def xid(self):
        if self.exaile is None:
            return None
        return self.exaile.gui.main.window.get_window().xid

    def unset_cover(self):
        self.awn.UnsetTaskIconByXid(self.xid())

    def cleanup(self):
        self.unset_cover()

    def set_cover(self, *args, **kwargs):
        if self.exaile is None:
            return
        elif not hasattr(self.exaile, 'player'):
            log.debug("Player not loaded, ignoring set_cover call")
            return

        try:
            os.remove(self.temp_icon_path)
        except (TypeError, OSError):
            pass

        if player.PLAYER.current is None:
            log.debug("Player stopped, removing AWN cover")
            self.unset_cover()
        elif not self.cover_display:
            self.unset_cover()
        else:
            image_data = covers.MANAGER.get_cover(player.PLAYER.current,
                                                  set_only=True, use_default=True)
            pixbuf = icons.MANAGER.pixbuf_from_data(image_data)
            descriptor, self.temp_icon_path = tempfile.mkstemp()
            pixbuf.save(self.temp_icon_path, 'png')
            self.awn.SetTaskIconByXid(self.xid(), self.temp_icon_path)

    def unset_timer(self):
        self._set_timer(100)

    def _set_timer(self, percent):
        if self.overlay == 'progress':
            self.awn.SetProgressByXid(self.xid(), percent)
        elif self.overlay == 'text':
            self.awn.SetProgressByXid(self.xid(), 100)
            if percent != 100 and percent != 0:
                self.awn.SetInfoByXid(self.xid(), "%d%%" % percent)
            else:
                self.awn.UnsetInfoByXid(self.xid())
        elif self.overlay == 'none':
            self.awn.SetProgressByXid(self.xid(), 100)
            self.awn.UnsetInfoByXid(self.xid())
        else:
            raise InvalidOverlayOption(self.overlay)

    def update_timer(self, *args, **kwargs):
        self.timer_id = None
        if self.exaile is None:
            return False
        if player.PLAYER is None:
            return False
        track = player.PLAYER.current
        # Not playing anything
        if track is None:
            return False
        # Streaming music
        if not track.is_local() and not track.get_tag_raw('__length'):
            self._set_timer(100)
            return False
        self._set_timer(int(player.PLAYER.get_progress() * 100))
        return True

    def on_option_set(self, event, settings, option):
        if option == 'plugin/awn/cover_display':
            self.set_cover()
        elif option == 'plugin/awn/overlay':
            self.update_timer()


EXAILE_AWN = None

TRACK_CHANGE_CALLBACKS = (
    'playback_current_changed',
    'playback_player_start',
    'playback_track_end',
    'player_loaded',
)


def enable(exaile):
    global EXAILE_AWN
    if EXAILE_AWN is None:
        EXAILE_AWN = ExaileAwn()
    EXAILE_AWN.exaile = exaile
    for signal in TRACK_CHANGE_CALLBACKS:
        xl.event.add_callback(EXAILE_AWN.set_cover, signal, player.PLAYER)
    xl.event.add_callback(EXAILE_AWN.enable_progress,
                          'playback_player_start', player.PLAYER)
    xl.event.add_callback(EXAILE_AWN.disable_progress,
                          'playback_player_end', player.PLAYER)
    xl.event.add_callback(EXAILE_AWN.toggle_pause_progress,
                          'playback_toggle_pause', player.PLAYER)
    xl.event.add_callback(EXAILE_AWN.on_option_set, 'plugin_awn_option_set')
    EXAILE_AWN.set_cover()


def disable(exaile):
    global EXAILE_AWN
    for signal in TRACK_CHANGE_CALLBACKS:
        xl.event.remove_callback(EXAILE_AWN.set_cover, signal)
    xl.event.remove_callback(EXAILE_AWN.enable_progress,
                             'playback_player_start', player.PLAYER)
    xl.event.remove_callback(EXAILE_AWN.disable_progress,
                             'playback_player_end', player.PLAYER)
    xl.event.remove_callback(EXAILE_AWN.toggle_pause_progress,
                             'playback_toggle_pause', player.PLAYER)
    EXAILE_AWN.unset_cover()
    EXAILE_AWN.unset_timer()
    EXAILE_AWN.exaile = None


def get_preferences_pane():
    return awn_prefs
