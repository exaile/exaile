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

from xl.nls import gettext as _

import urlparse, urllib, logging, time
import gst, gobject
from xl import common, event
from xl.player import pipe, _base

logger = logging.getLogger(__name__)


class NormalPlayer(_base.ExailePlayer):
    def __init__(self):
        _base.ExailePlayer.__init__(self,
                pre_elems=[pipe.ProviderBin("stream_element")])

        self._current = None
        self.playbin = None
        self.bus = None

        self.setup_pipe()

    def setup_pipe(self):
        self.setup_playbin()
        self.setup_bus()
        self.setup_gst_elements()

    def setup_playbin(self):
        """
            setup the playbin to use for playback
        """
        self.playbin = gst.element_factory_make("playbin", "player")

    def setup_bus(self):
        """
            setup the gstreamer message bus and callacks
        """
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('message', self.on_message)

    def setup_gst_elements(self):
        """
            sets up additional gst elements
        """
        self.playbin.set_property("audio-sink", self.mainbin)

    def eof_func(self, *args):
        """
            called at the end of a stream
        """
        self._queue.next()

    def on_message(self, bus, message, reading_tag = False):
        """
            Called when a message is received from gstreamer
        """
        if message.type == gst.MESSAGE_TAG and self.tag_func:
            self.tag_func(message.parse_tag())
            if not self.current.get_tag_raw('__length'):
                try:
                    duration = float(self.playbin.query_duration(
                            gst.FORMAT_TIME, None)[0])/1000000000
                    if duration > 0:
                        self.current.set_tag_raw('__length', duration)
                except gst.QueryError:
                    logger.error("Couldn't query duration")
        elif message.type == gst.MESSAGE_EOS and not self.is_paused():
            self.eof_func()
        elif message.type == gst.MESSAGE_ERROR:
            logger.error("%s %s" %(message, dir(message)) )
            a = message.parse_error()[0]
            gobject.idle_add(self._on_playback_error, a.message)

            # TODO: merge this into stop() and make it engine-agnostic somehow
            curr = self.current
            self._current = None
            self.playbin.set_state(gst.STATE_NULL)
            self.setup_pipe()
            event.log_event("playback_track_end", self, curr)
            event.log_event("playback_player_end", self, curr)
            gobject.idle_add(self.eof_func)
        elif message.type == gst.MESSAGE_BUFFERING:
            percent = message.parse_buffering()
            if not percent < 100:
                logger.info('Buffering complete')
            if percent % 5 == 0:
                event.log_event('playback_buffering', self, percent)
        return True

    def _get_current(self):
        return self._current

    def _get_gst_state(self):
        """
            Returns the raw GStreamer state
        """
        return self.playbin.get_state(timeout=50*gst.MSECOND)[1]

    def get_position(self):
        """
            Gets the current playback position of the playing track
        """
        if self.is_paused(): return self._last_position
        try:
            self._last_position = \
                self.playbin.query_position(gst.FORMAT_TIME)[0]
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
        source = self.playbin.get_property('source')
        device = self.current.get_loc_for_io().split("#")[-1]
        source.set_property('device', device)
        self.playbin.disconnect(self.notify_id)

    def play(self, track):
        """
            plays the specified track, overriding any currently playing track

            if the track cannot be played, playback stops completely
        """
        if track is None:
            self.stop()
            return False
        else:
            self.stop(fire=False)

        playing = self.is_playing()

        self._current = track

        uri = track.get_loc_for_io()
        logger.info("Playing %s" % uri)
        self.reset_playtime_stamp()

        self.playbin.set_property("uri", uri)
        if urlparse.urlsplit(uri)[0] == "cdda":
            self.notify_id = self.playbin.connect('notify::source',
                    self.__notify_source)

        self.playbin.set_state(gst.STATE_PLAYING)
        if not playing:
            event.log_event('playback_player_start', self, track)
        event.log_event('playback_track_start', self, track)

        return True

    def stop(self, fire=True):
        """
            stop playback
        """
        if self.is_playing() or self.is_paused():
            self.update_playtime()
            current = self.current
            self.playbin.set_state(gst.STATE_NULL)
            self._current = None
            event.log_event('playback_track_end', self, current)
            if fire:
                event.log_event('playback_player_end', self, current)
            return True
        return False

    def pause(self):
        """
            pause playback. DOES NOT TOGGLE
        """
        if self.is_playing():
            self.update_playtime()
            self.playbin.set_state(gst.STATE_PAUSED)
            self.reset_playtime_stamp()
            event.log_event('playback_player_pause', self, self.current)
            return True
        return False

    def unpause(self):
        """
            unpause playback
        """
        if self.is_paused():
            self.reset_playtime_stamp()

            # gstreamer does not buffer paused network streams, so if the user
            # is unpausing a stream, just restart playback
            if not (self.current.is_local() or
                    self.current.get_tag_raw('__length')):
                self.playbin.set_state(gst.STATE_READY)

            self.playbin.set_state(gst.STATE_PLAYING)
            event.log_event('playback_player_resume', self, self.current)
            return True
        return False

    def seek(self, value):
        """
            seek to the given position in the current stream
        """
        value = int(gst.SECOND * value)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH,
            gst.SEEK_TYPE_SET, value, gst.SEEK_TYPE_NONE, 0)

        res = self.playbin.send_event(event)
        if res:
            self.playbin.set_new_stream_time(0L)
        else:
            logger.debug("Couldn't send seek event")

        self.last_seek_pos = value

