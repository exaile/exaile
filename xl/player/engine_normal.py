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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
import gst

from xl.nls import gettext as _
from xl import common, event, settings
from xl.player import pipe, _base

logger = logging.getLogger(__name__)


class NormalPlayer(_base.ExailePlayer):
    def __init__(self, name):
        gst.init()
        self._last_position = 0
        self._current = None
        self._buffered_track = None
        self._fakevideo = None
        _base.ExailePlayer.__init__(self, name,
                pre_elems=[pipe.ProviderBin( self, "stream_element")])

    def _setup_pipe(self):
        """
            setup the playbin to use for playback
        """
        self._pipe = gst.element_factory_make("playbin2", "player")
        self._pipe.connect("about-to-finish", self._on_about_to_finish)
        self._fakevideo = gst.element_factory_make("fakesink")
        self._fakevideo.set_property("sync", True)
        self._pipe.set_property("audio-sink", self._mainbin)
        self._pipe.set_property("video-sink", self._fakevideo)

    def _eos_func(self, *args):
        """
            called at the end of a stream
        """
        track = None
        if settings.get_option("%s/auto_advance" % self._name, True):
            track = self.queue.next()
            
        if track is None:
            self.stop()

    def _on_about_to_finish(self, pbin):
        '''
            This function exists solely to allow gapless playback for audio
            formats that support it. Setting the URI property of the playbin
            will queue the track for playback immediately after the previous 
            track.
        '''
        if settings.get_option("%s/auto_advance" % self._name, True):
            track = self.queue.get_next()
            if track:
                uri = track.get_loc_for_io()
                self._pipe.set_property("uri", uri)
                self._buffered_track = track
            

    def _handle_message(self, bus, message, reading_tag = False):
        
        if message.type == gst.MESSAGE_BUFFERING:
            percent = message.parse_buffering()
            if not percent < 100:
                logger.info('Buffering complete')
            if percent % 5 == 0:
                event.log_event('playback_buffering', self, percent)
                
        elif message.type == gst.MESSAGE_ELEMENT and \
                message.src == self._pipe and \
                message.structure.get_name() == 'playbin2-stream-changed' and \
                self._buffered_track is not None:
            self.queue.next(autoplay=False)
            self._next_track(self._buffered_track, already_playing=True)
            
        else:
            return False
        return True

    def _error_func(self):
        
        # No need to reinitialize more than once
        if self._pipe.get_state(timeout=50*gst.MSECOND)[1] == gst.STATE_NULL:
            return
        
        self.stop()
        self._pipe.set_state(gst.STATE_NULL)
        self._pipe.set_property('audio-sink', None)
        
        # The mainbin is still connected to the old element, need to
        # disconnect it and flush it.
        self._mainbin.unparent()
        
        # Only flush the element if necessary
        if self._mainbin.get_state(timeout=50*gst.MSECOND)[1] != gst.STATE_NULL:
        
            # flush it
            sinkpad = self._mainbin.get_static_pad('sink')
            self._err_probe_id = sinkpad.add_event_probe(self._error_func_flush)
            
            sinkpad.send_event(gst.event_new_eos())
            
        else:
            self._reinitialize()
    
    def _error_func_flush(self, pad, info):
        
        # wait for end of stream marker
        if info.type != gst.EVENT_EOS:
            return True
        
        pad.remove_event_probe(self._err_probe_id)
        self._pad_event_probe_id = None
        
        # Finish clearing the element
        self._mainbin.set_state(gst.STATE_NULL)    
            
        # Finally, reinitialize the pipe/bus now that the mainbin is ready
        self._reinitialize()
        
        return False
    
    def _reinitialize(self):
        self._setup_pipe()
        self._setup_bus()

    def _get_current(self):
        return self._current

    def get_position(self):
        """
            Gets the current playback position of the playing track
        """
        if not self.is_paused():
            try:
                self._last_position = \
                    self._pipe.query_position(gst.FORMAT_TIME)[0]
            except gst.QueryError:
                self._last_position = 0
        return self._last_position

    def _update_playtime(self):
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

    def _reset_playtime_stamp(self):
        self._playtime_stamp = int(time.time())

    def __notify_source(self, *args):
        # this is for handling multiple CD devices properly
        source = self._pipe.get_property('source')
        device = self.current.get_loc_for_io().split("#")[-1]
        source.set_property('device', device)
        self._pipe.disconnect(self.notify_id)

    def _next_track(self, track, already_playing=False):
        """
            internal api: advances the track to the next track
        """
        if track is None:
            self.stop()
            return False
        elif not already_playing:
            self.stop(_fire=False)
        else:
            self.stop(_fire=False, _onlyfire=True)

        playing = self.is_playing()

        if not playing:
            event.log_event('playback_reconfigure_bins', self, None)

        self._current = track

        uri = track.get_loc_for_io()
        logger.info("Playing %s" % common.sanitize_url(uri))
        self._reset_playtime_stamp()
        
        if not already_playing:
            self._pipe.set_property("uri", uri)
            if urlparse.urlsplit(uri)[0] == "cdda":
                self.notify_id = self._pipe.connect('notify::source',
                        self.__notify_source)
            
            self._pipe.set_state(gst.STATE_PLAYING)
        
        if not playing:
            event.log_event('playback_player_start', self, track)
        event.log_event('playback_track_start', self, track)
        
        if playing and self._should_delay_start():
            self._last_position = 0
        
        self._setup_startstop_offsets(track)
        
        return True
        
    def play(self, track):
        """
            plays the specified track, overriding any currently playing track

            if the track cannot be played, playback stops completely
        """
        return self._next_track(track)
        

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
        self._buffered_track = None
        current = self.current
        if not _onlyfire:
            self._pipe.set_state(gst.STATE_NULL)
        self._update_playtime()
        self._current = None
        event.log_event('playback_track_end', self, current)
        return current

    def _pause(self):
        self._update_playtime()
        self._pipe.set_state(gst.STATE_PAUSED)
        self._reset_playtime_stamp()

    def _unpause(self):
        self._reset_playtime_stamp()

        # gstreamer does not buffer paused network streams, so if the user
        # is unpausing a stream, just restart playback
        if not (self.current.is_local() or
                self.current.get_tag_raw('__length')):
            self._pipe.set_state(gst.STATE_READY)

        self._pipe.set_state(gst.STATE_PLAYING)

    def seek(self, value):
        """
            seek to the given position in the current stream
        """
        new_position = int(gst.SECOND * value)
        seek_event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH, gst.SEEK_TYPE_SET,
            new_position,
            gst.SEEK_TYPE_NONE, 0)

        # FIXME: GI: Broken
        res = None #self._pipe.send_event(seek_event)
        if res:
            self._pipe.set_new_stream_time(0L)
            # update this in case we're paused
            self._last_position = new_position  
            event.log_event('playback_seeked', self, value)
        else:
            logger.debug("Couldn't send seek event")

