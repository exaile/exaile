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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import logging
import time

import pygst
pygst.require('0.10')
import gst

from xl import event, settings, common
from xl.player import pipe
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
        event.add_callback(self._on_setting_change, 'player_option_set')
        event.add_callback(self._on_track_end, 'playback_track_end', self)

    def _on_setting_change(self, name, object, data):
        if data == "player/volume":
            self._load_volume()

    def _on_track_end(self, name, obj, track):
        if not track:
            return
        try:
            i = int(track.get_tag_raw('__playcount'))
        except:
            i = 0
        track.set_tag_raw('__playcount', i + 1)
        track.set_tag_raw('__last_played', time.time())

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

    def scroll(self, value):
        # Getting new position
        tm = self.get_time() + value

        # If we are before the beginning of the track, restart it or go to prev
        if tm < 0:
            self._queue.prev()
            return

        # If we are after the end of the track, switch to the next one
        elif tm > self.current.get_tag_raw('__length'):
            self._queue.next()
            return

        # Apply new position
        self.seek(tm)

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
            progress = self.get_position()/float(
                    self.current.get_tag_raw("__length")*gst.SECOND)
        except TypeError: # track doesnt have duration info
            progress = 0
        except AttributeError: # no current track
            progress = 0
        else:
            if progress < 0:
                progress = 0
            elif progress > 1:
                progress = 1
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

    @staticmethod
    def parse_stream_tags(track, tags):
        """
            Called when a tag is found in a stream.
        """
        newsong=False

        for key in tags.keys():
            value = tags[key]
            try:
                value = common.to_unicode(value)
            except UnicodeDecodeError:
                logger.debug('  ' + key + " [can't decode]: " + `str(value)`)
                continue # TODO: What encoding does gst give us?

            value = [value]

            if key == '__bitrate':
                track.set_tag_raw('__bitrate', int(value[0]) / 1000)

            # if there's a comment, but no album, set album to the comment
            elif key == 'comment' and not track.get_tag_raw('album'):
                track.set_tag_raw('album', value)

            elif key == 'album': track.set_tag_raw('album', value)
            elif key == 'artist': track.set_tag_raw('artist', value)
            elif key == 'duration': track.set_tag_raw('__length',
                    float(value[0])/1000000000)
            elif key == 'track-number': track.set_tag_raw('tracknumber', value)
            elif key == 'genre': track.set_tag_raw('genre', value)

            elif key == 'title':
                try:
                    if track.get_tag_raw('__rawtitle') != value:
                        track.set_tag_raw('__rawtitle', value)
                        newsong = True
                except AttributeError:
                    track.set_tag_raw('__rawtitle', value)
                    newsong = True

                title_array = value[0].split(' - ', 1)
                if len(title_array) == 1 or \
                        track.get_loc_for_io().lower().endswith(".mp3"):
                    track.set_tag_raw('title', value)
                else:
                    track.set_tag_raw('artist', [title_array[0]])
                    track.set_tag_raw('title', [title_array[1]])



        return newsong

