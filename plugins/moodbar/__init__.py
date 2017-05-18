# moodbar - Replace Exaile's seekbar with a moodbar
# Copyright (C) 2015  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Ideas taken from:
# - The original Moodbar visualization method in Amarok 1;
# - The previous Moodbar plugin included in Exaile <4, by Solyanov Michael.


from __future__ import division, print_function

import os.path

from gi.repository import (
    Gdk,
    GLib,
)

import xl.event
from xl.nls import gettext as _
import xl.player
import xl.xdg
import xlgui.guiutil

from cache import ExaileMoodbarCache
from generator import SpectrumMoodbarGenerator
from widget import Moodbar


class MoodbarPlugin:

    exaile = None
    generator = None
    cache = None

    def __init__(self):
        self.main_controller = self.preview_controller = None

    def enable(self, exaile):
        self.generator = SpectrumMoodbarGenerator()
        self.generator.check()

        self.exaile = exaile
        self.cache = ExaileMoodbarCache(os.path.join(xl.xdg.get_cache_dir(), 'moods'))

        xl.event.add_ui_callback(self._on_preview_device_enabled, 'preview_device_enabled')
        xl.event.add_ui_callback(self._on_preview_device_disabling, 'preview_device_disabling')
        previewdevice = exaile.plugins.enabled_plugins.get('previewdevice', None)
        if previewdevice:
            self.on_preview_device_enabled('', previewdevice)

    def on_gui_loaded(self):
        self.main_controller = MoodbarController(self, xl.player.PLAYER, self.exaile.gui.main.progress_bar)

    def disable(self, exaile):
        if not self.main_controller:  # Disabled more than once or before gui_loaded
            return
        xl.event.remove_callback(self._on_preview_device_enabled, 'preview_device_enabled')
        xl.event.remove_callback(self._on_preview_device_disabling, 'preview_device_disabling')
        self.main_controller.destroy()
        if self.preview_controller:
            self.preview_controller.destroy()
        self.main_controller = self.preview_controller = None
        del self.exaile, self.cache, self.generator

    # Preview Device events

    def _on_preview_device_enabled(self, event, plugin, _=None):
        self.preview_controller = MoodbarController(self, plugin.player, plugin.progress_bar)

    def _on_preview_device_disabling(self, event, plugin, _=None):
        self.preview_controller.destroy()
        self.preview_controller = None

plugin_class = MoodbarPlugin


# TRANSLATORS: Time format for playback progress
def format_time(seconds, time_format=_("{minutes}:{seconds:02}")):
    seconds = int(round(seconds))
    minutes, seconds = divmod(seconds, 60)
    return time_format.format(minutes=int(minutes), seconds=seconds)


class MoodbarController:

    def __init__(self, plugin, player, orig_seekbar):
        self.plugin = plugin
        self.player = player
        self.orig_seekbar = orig_seekbar
        self.timer = self.seeking = False

        self.moodbar = moodbar = Moodbar()
        moodbar.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        xlgui.guiutil.gtk_widget_replace(self.orig_seekbar, moodbar)
        moodbar.show()
        # TODO: If currently playing, this needs to run now as well:
        xl.event.add_ui_callback(self._on_playback_track_start, 'playback_track_start', self.player)
        xl.event.add_ui_callback(self._on_playback_track_end, 'playback_track_end', self.player)
        moodbar.connect('button-press-event', self._on_moodbar_button_press)
        moodbar.connect('motion-notify-event', self._on_moodbar_motion)
        moodbar.connect('button-release-event', self._on_moodbar_button_release)

    def destroy(self):
        xl.event.remove_callback(self._on_playback_track_end, 'playback_track_start', self.player)
        xl.event.remove_callback(self._on_playback_track_end, 'playback_track_end', self.player)
        if self.timer:
            GLib.source_remove(self.timer)
        assert self.orig_seekbar
        xlgui.guiutil.gtk_widget_replace(self.moodbar, self.orig_seekbar)
        self.moodbar.destroy()
        self.moodbar = None

    # Playback events

    def _on_playback_track_start(self, event, player, track):
        cache = self.plugin.cache
        uri = player.current.get_loc_for_io()
        data = cache.get(uri) if cache else None
        self.moodbar.set_mood(data)
        self._on_timer()
        self.timer = GLib.timeout_add_seconds(1, self._on_timer)
        if not data and uri.startswith('file://'):
            def callback(uri, data):
                if cache:
                    cache.put(uri, data)
                self.moodbar.set_mood(data)
            self.plugin.generator.generate_async(uri, callback)

    def _on_timer(self):
        assert self.moodbar
        try:
            total_time = self.player.current.get_tag_raw('__length')
        except AttributeError:  # No current track
            return False
        current_time = self.player.get_time()
        if total_time:
            time_format = dict(
                current=format_time(current_time),
                remaining=format_time(total_time - current_time),
            )
            # TRANSLATORS: Format for playback progress text
            self.moodbar.set_text(_("{current} / {remaining}").format(**time_format))
            if not self.seeking:
                self.moodbar.seek_position = current_time / total_time
        else:
            self.moodbar.set_text(format_time(current_time))
        return True

    def _on_playback_track_end(self, event, player, track):
        GLib.source_remove(self.timer)
        self.timer = None
        self.moodbar.set_mood(None)
        self.moodbar.seek_position = None
        self.moodbar.set_text(None)

    # Mouse events

    def _on_moodbar_button_press(self, moodbar, event):
        """
        :type moodbar: Moodbar
        :type event: Gdk.Event
        """
        if event.button == Gdk.BUTTON_PRIMARY:
            self.seeking = True
            self._on_moodbar_motion(moodbar, event)

    def _on_moodbar_motion(self, moodbar, event):
        """
        :type moodbar: Moodbar
        :type event: Gdk.Event
        """
        if self.seeking:
            w = moodbar.get_allocation().width
            x = event.get_coords()[0]
            x = max(0, min(x, w))
            moodbar.seek_position = x / w

    def _on_moodbar_button_release(self, moodbar, event):
        """
        :type moodbar: Moodbar
        :type event: Gdk.Event
        """
        if event.button == Gdk.BUTTON_PRIMARY and self.seeking:
            self.player.set_progress(moodbar.seek_position)
            self.seeking = False


# vi: et sts=4 sw=4 tw=99
