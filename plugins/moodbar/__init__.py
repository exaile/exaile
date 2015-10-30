# Johannes Sasongko <sasongko@gmail.com>, 2015


from __future__ import division, print_function

import os.path

from gi.repository import GLib

import xl.event
from xl.nls import gettext as _
import xl.player
import xl.xdg
import xlgui.guiutil

from cache import ExaileMoodbarCache
from generator import SpectrumMoodbarGenerator
from painter import MoodbarPainter
from widget import Moodbar


# TRANSLATORS: Time format for playback progress
TIME_FORMAT = _("{minutes}:{seconds:02}")

def format_time(seconds):
    seconds = int(round(seconds))
    minutes, seconds = divmod(seconds, 60)
    return TIME_FORMAT.format(minutes=int(minutes), seconds=seconds)


class MoodbarPlugin:
    def __init__(self, player=None):
        if not player:
            self.player = xl.player.PLAYER

    def enable(self, exaile):
        self.exaile = exaile
        self.cache = ExaileMoodbarCache(os.path.join(xl.xdg.get_cache_dir(), 'moods'))
        self.generator = SpectrumMoodbarGenerator()
        self.moodbar = None
        self.timer = None

    def on_gui_loaded(self):
        self.moodbar = Moodbar(MoodbarPainter())
        self.orig_seekbar = self.exaile.gui.main.progress_bar
        xlgui.guiutil.gtk_widget_replace(self.orig_seekbar, self.moodbar)
        xl.event.add_ui_callback(self._on_playback_track_start, 'playback_track_start', self.player)
        xl.event.add_ui_callback(self._on_playback_track_end, 'playback_track_end', self.player)
        #event.add_callback(..., 'preview_device_enabled')
        #event.add_callback(..., 'preview_device_disabling')

    def disable(self, exaile):
        if not self.moodbar:
            return
        assert self.orig_seekbar
        xlgui.guiutil.gtk_widget_replace(self.moodbar, self.orig_seekbar)
        self.moodbar.destroy()
        self.moodbar = None

    def _on_playback_track_start(self, event, player, track):
        uri = player.current.get_loc_for_io()
        data = self.cache.get(uri)
        self.moodbar.set_mood(data)
        self._on_timer()
        self.timer = GLib.timeout_add_seconds(1, self._on_timer)
        if not data and uri.startswith('file://'):
            def callback(uri, data):
                self.cache.put(uri, data)
                self.moodbar.set_mood(data)
            self.generator.generate_async(uri, callback)

    def _on_timer(self):
        try:
            total_time = self.player.current.get_tag_raw('__length')
        except AttributeError:  # No current track
            return False
        current_time = self.player.get_time()
        if total_time:
            format = dict(
                current=format_time(current_time),
                remaining=format_time(total_time - current_time),
            )
            # TRANSLATORS: Format for playback progress text
            self.moodbar.set_text(_("{current} / {remaining}").format(**format))
            self.moodbar.set_seek_position(current_time / total_time)
        else:
            self.moodbar.set_text(format_time(current_time))
        return True

    def _on_playback_track_end(self, event, player, track):
        GLib.source_remove(self.timer)
        self.timer = None
        self.moodbar.set_mood(None)

plugin_class = MoodbarPlugin
