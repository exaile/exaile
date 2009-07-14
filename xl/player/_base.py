# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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

import pygst
pygst.require('0.10')
import gst

from xl import event, settings
from xl.player import pipe
import logging
logger = logging.getLogger(__name__)




class ExailePlayer(object):
    """
        Base class all players must inherit from and implement.
    """
    def __init__(self, pre_elems=[]):
        self._queue = None
        self._playtime_stamp = None
        self._last_position = 0

        self.mainbin = pipe.MainBin(pre_elems=pre_elems)

        self._load_volume()
        event.add_callback(self._on_setting_change, 'option_set')
        event.add_callback(self._on_track_end, 'playback_track_end', self)

    def _on_setting_change(self, name, object, data):
        if data == "player/volume":
            self._load_volume()

    def _on_track_end(self, name, object, track):
        try:
            i = int(track['playcount'])
        except:
            i = 0
        track['playcount'] = i + 1

    def _load_volume(self):
        """
            load volume from settings
        """
        volume = settings.get_option("player/volume", 1)
        self._set_volume(volume)

    def _set_queue(self, queue):
        self._queue = queue

    def _get_volume(self):
        """
            Gets the current actual volume.  This does not reflect what is
            shown to the user, see the player/volume setting for that.
        """
        return self.mainbin.get_volume()

    def _set_volume(self, volume):
        """
            Sets the volume. This does NOT update the setting value,
            and should be used only internally.
        """
        self.mainbin.set_volume(volume)

    def get_volume(self):
        """
            Gets the current volume percentage
        """
        return (settings.get_option("player/volume", 1) * 100)

    def set_volume(self, volume):
        """
            Sets the current volume percentage
        """
        volume = min(volume, 100)
        volume = max(0, volume)
        settings.set_option("player/volume", volume / 100.0)

    def _get_current(self):
        raise NotImplementedError

    def __get_current(self):
        return self._get_current()
    current = property(__get_current)

    def play(self, track):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def unpause(self):
        raise NotImplementedError

    def toggle_pause(self):
        if self.is_paused():
            self.unpause()
        else:
            self.pause()

        event.log_event("playback_toggle_pause", self, self.current)

    def seek(self, value):
        raise NotImplementedError

    def get_position(self):
        """
            Gets the current playback position of the playing track
        """
        raise NotImplementedError

    def get_time(self):
        """
            Gets current playback time in seconds
        """
        return self.get_position()/gst.SECOND        

    def get_progress(self):
        try:
            progress = self.get_time()/float(self.current.get_duration())
        except ZeroDivisionError: # track doesnt have duration info
            progress = 0
        except AttributeError: # no current track
            progress = 0
        except AttributeError:
            progress = -1
        return progress

    def _get_gst_state(self):
        """
            Returns the raw GStreamer state
        """
        raise NotImplementedError

    def get_state(self):
        """
            Get player state

            returns one of "playing", "paused", "stopped"
        """        
        state = self._get_gst_state()
        if state == gst.STATE_PLAYING:
            return 'playing'
        elif state == gst.STATE_PAUSED:
            return 'paused'
        else:
            return 'stopped'

    def is_playing(self):
        return self._get_gst_state() == gst.STATE_PLAYING

    def is_paused(self):
        return self._get_gst_state() == gst.STATE_PAUSED

    def _on_playback_error(self, message):
        """
            Called when there is an error during playback
        """
        event.log_event('playback_error', self, message, async=False)
        self.stop()

    def tag_func(self, *args):
        event.log_event('tags_parsed', self, (self.current, args[0]))


