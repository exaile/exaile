# Copyright (C) 2008-2010 Adam Olsen
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
import urllib
import urlparse

import glib
import pygst
pygst.require('0.10')
import gst

from xl.nls import gettext as _
from xl import common, event
from xl.player import pipe, _base

logger = logging.getLogger(__name__)


class NormalPlayer(_base.ExailePlayer):
    def __init__(self):
        self._current = None
        self.fakevideo = None
        _base.ExailePlayer.__init__(self,
                pre_elems=[pipe.ProviderBin("stream_element")])

    def _setup_pipe(self):
        """
            setup the playbin to use for playback
        """
        self.pipe = gst.element_factory_make("playbin2", "player")
        self.pipe.connect("about-to-finish", self.on_about_to_finish)
        self.fakevideo = gst.element_factory_make("fakesink")
        self.fakevideo.set_property("sync", True)
        self.pipe.set_property("audio-sink", self.mainbin)
        self.pipe.set_property("video-sink", self.fakevideo)

    def eos_func(self, *args):
        """
            called at the end of a stream
        """
        self._queue.next()

    def on_about_to_finish(self, pbin):
        tr = self._queue.next(autoplay=False)
        if tr:
            self.play(tr, stop_last=False)
        else:
            glib.idle_add(self.stop)

    def _handle_message(self, bus, message, reading_tag = False):
        if message.type == gst.MESSAGE_BUFFERING:
            percent = message.parse_buffering()
            if not percent < 100:
                logger.info('Buffering complete')
            if percent % 5 == 0:
                event.log_event('playback_buffering', self, percent)
        else:
            return False
        return True

    def error_func():
        # TODO: merge this into stop() and make it engine-agnostic somehow
        curr = self.current
        self._current = None
        self.pipe.set_state(gst.STATE_NULL)
        self.setup_pipe()
        event.log_event("playback_track_end", self, curr)
        event.log_event("playback_player_end", self, curr)

    def _get_current(self):
        return self._current

    def get_position(self):
        """
            Gets the current playback position of the playing track
        """
        if self.is_paused():
            return self._last_position
        try:
            self._last_position = \
                self.pipe.query_position(gst.FORMAT_TIME)[0]
        except gst.QueryError:
            self._last_position = 0

        return self._last_position

    def update_playtime(self):
        """
            updates the total playtime for the currently playing track
        """
        if self.current and self._playtime_stamp:
            last = self.current.get_tag_raw('__playtime')
            if type(last) == str:
                try:
                    last = int(last)
                except:
                    last = 0
            elif type(last) != int:
                last = 0
            self.current.set_tag_raw('__playtime', last + int(time.time() - \
                    self._playtime_stamp))
            self._playtime_stamp = None

    def reset_playtime_stamp(self):
        self._playtime_stamp = int(time.time())

    def __notify_source(self, *args):
        # this is for handling multiple CD devices properly
        source = self.pipe.get_property('source')
        device = self.current.get_loc_for_io().split("#")[-1]
        source.set_property('device', device)
        self.pipe.disconnect(self.notify_id)

    def play(self, track, stop_last=True):
        """
            plays the specified track, overriding any currently playing track

            if the track cannot be played, playback stops completely
        """
        if track is None:
            self.stop()
            return False
        elif stop_last:
            self.stop(_fire=False)
        else:
            self.stop(_fire=False, _onlyfire=True)

        playing = self.is_playing()

        if not playing:
            event.log_event('playback_reconfigure_bins', self, None)

        self._current = track

        uri = track.get_loc_for_io()
        logger.info("Playing %s" % uri)
        self.reset_playtime_stamp()

        self.pipe.set_property("uri", uri)
        if urlparse.urlsplit(uri)[0] == "cdda":
            self.notify_id = self.pipe.connect('notify::source',
                    self.__notify_source)

        self.pipe.set_state(gst.STATE_PLAYING)
        if not playing:
            event.log_event('playback_player_start', self, track)
        event.log_event('playback_track_start', self, track)

        return True

    # FIXME: these parameters are really bad
    def _stop(self, _onlyfire=False):
        """
            Stops playback.

            The following parameters are for internal use only and are
            not public API.

            :param onlyfire: Only send the _end event(s), don't actually
                         halt playback. This is used at the end of a playlist,
                         because the gapless mechanism will fire to tell us to
                         load the next track for buffering, but since there
                         isn't one if we actually halt the player the last few
                         moments of the prior track will be cut off.
        """
        self.update_playtime()
        current = self.current
        if not _onlyfire:
            self.pipe.set_state(gst.STATE_NULL)
        self._current = None
        event.log_event('playback_track_end', self, current)
        return current

    def _pause(self):
        self.update_playtime()
        self.pipe.set_state(gst.STATE_PAUSED)
        self.reset_playtime_stamp()

    def _unpause(self):
        self.reset_playtime_stamp()

        # gstreamer does not buffer paused network streams, so if the user
        # is unpausing a stream, just restart playback
        if not (self.current.is_local() or
                self.current.get_tag_raw('__length')):
            self.pipe.set_state(gst.STATE_READY)

        self.pipe.set_state(gst.STATE_PLAYING)

    def seek(self, value):
        """
            seek to the given position in the current stream
        """
        value = int(gst.SECOND * value)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH, gst.SEEK_TYPE_SET, value,
            gst.SEEK_TYPE_NONE, 0)

        res = self.pipe.send_event(event)
        if res:
            self.pipe.set_new_stream_time(0L)
        else:
            logger.debug("Couldn't send seek event")

        self.last_seek_pos = value

