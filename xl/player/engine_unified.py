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
import threading
import time

from gi.repository import GLib
from gi.repository import Gst

from xl.nls import gettext as _
from xl import event, settings, common
from xl.player import _base, pipe

logger = logging.getLogger(__name__)

class UnifiedPlayer(_base.ExailePlayer):
    def __init__(self, name):
        Gst.init()
        self.caps = None
        self.adder = None
        self.audio_queue = None
        _base.ExailePlayer.__init__(self, name)
        self._current_stream = 1
        self._timer_id = 0
        self.streams = [None, None]

    def _setup_pipe(self):
        self.caps = Gst.Caps.from_string('audio/x-raw')
        self._pipe = Gst.Pipeline()
        self.adder = Gst.ElementFactory.make("adder")
        self.audio_queue = Gst.ElementFactory.make("queue")
        self._load_queue_values()
        for e in (self.adder, self.audio_queue, self._mainbin):
            self._pipe.add(e)
        self.adder.link(self.audio_queue)
        self.audio_queue.link(self._mainbin)

    def _load_queue_values(self):
        # queue defaults to 1 second of audio data, however this
        # means that there's a 1 second delay between the UI and
        # the audio! Thus we reset it to 1/10 of a second, which
        # is small enough to be unnoticeable while still maintaining
        # a decent buffer. This is done as a setting so users whose
        # collections are on slower media can increase it to preserve
        # gapless, at the expense of UI lag.
        self.audio_queue.set_property("max-size-time",
                settings.get_option("%s/queue_duration" % self._name, 1000000))

    def _on_drained(self, dec, stream):
        logger.debug("%s drained"%stream.get_name())
        #if stream.track != self.current:
        #    return
        if not settings.get_option("%s/crossfading" % self._name, False):
            tr = None
            if settings.get_option("%s/auto_advance" % self._name, True):
                tr = self.queue.next(autoplay=False)
            self.unlink_stream(stream)
            if tr is None:
                self.stop()
            else:
                self.play(tr, user=False)
        else:
            self.unlink_stream(stream)

    def _get_current(self):
        if self.streams[self._current_stream]:
            return self.streams[self._current_stream].get_current()

    def get_position(self):
        try:
            return self.streams[self._current_stream].get_position()
        except AttributeError:
            return 0

    @common.synchronized
    def play(self, track, user=True):
        if not track:
            return # we cant play nothing

        playing = self.is_playing()

        logger.debug("%s: Attempting to play \"%s\""% (self._name, track))
        next = 1-self._current_stream

        if self.streams[next]:
            self.unlink_stream(self.streams[next])

        fading = False
        duration = 0

        if user:
            if settings.get_option("%s/user_fade_enabled" % self._name, False):
                fading = True
                duration = settings.get_option("%s/user_fade" % self._name, 1000)
            else:
                self.unlink_stream(self.streams[self._current_stream])
        else:
            if settings.get_option("%s/crossfading" % self._name, False):
                fading = True
                duration = settings.get_option(
                        "%s/crossfade_duration" % self._name, 3000)
            else:
                self.unlink_stream(self.streams[self._current_stream])

        if not playing:
            event.log_event('playback_reconfigure_bins', self, None)

        self.streams[next] = AudioStream("Stream%s"%(next), self, caps=self.caps)
        self.streams[next].dec.connect("drained", self._on_drained,
                self.streams[next])

        if not self.link_stream(self.streams[next], track):
            return False

        if fading:
            self.streams[next].set_volume(0)

        self._pipe.set_state(Gst.State.PLAYING)
        self.streams[next]._settle_flag = 1
        GLib.idle_add(self.streams[next].set_state, Gst.State.PLAYING)
        GLib.idle_add(self._set_state, self._pipe, Gst.State.PLAYING)

        if fading:
            timeout = int(float(duration)/float(100))
            if self.streams[next]:
                GLib.timeout_add(timeout, self._fade_stream,
                        self.streams[next], 1)
            if self.streams[self._current_stream]:
                GLib.timeout_add(timeout, self._fade_stream,
                        self.streams[self._current_stream], -1, True)
            if settings.get_option("%s/crossfading" % self._name, False):
                time = int(track.get_tag_raw("__length")*1000 - duration)
                GLib.timer_id = GLib.timeout_add(time,
                        self._start_crossfade)

        self._current_stream = next
        if not playing:
            event.log_event('playback_player_start', self, track)
        event.log_event('playback_track_start', self, track)

        return True

    def _set_state(self, thing, state):
        ret = thing.set_state(state)
        if ret == Gst.StateChangeReturn.SUCCESS:
            return False
        else:
            return True

    def _fade_stream(self, stream, direction, delete=False):
        current = stream.get_volume()
        current += direction/100.0
        stream.set_volume(current)
        if delete and current < 0.01:
            self.unlink_stream(stream)
            return False
        return 0.01 <= current <= 1

    def _start_crossfade(self, *args):
        tr = None
        if settings.get_option("%s/auto_advance" % self._name, True):
            tr = self.queue.next(autoplay=False)
        if tr is not None:
            self.play(tr, user=False)
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        if tr is None:
            self._timer_id = GLib.timeout_add(1000 * \
                    (self.current.get_tag_raw('__length') - self.get_time()),
                    self.stop)
        return False

    def _reset_crossfade_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        if not self.is_playing():
            return
        if not settings.get_option("%s/crossfading" % self._name, False):
            return
        duration = settings.get_option("%s/crossfade_duration" % self._name, 3000)
        time = int( self.current.get_tag_raw('__length')*1000 - \
                (self.get_time()*1000 + duration) )
        if time < duration: # start crossfade now, we're late!
            GLib.idle_add(self._start_crossfade)
        else:
            self._timer_id = GLib.timeout_add(time, self._start_crossfade)

    def unlink_stream(self, stream):
        try:
            current = stream.get_track()
            pad = stream.get_static_pad("src").get_peer()
            stream.unlink(self.adder)
            try:
                self.adder.release_request_pad(pad)
            except TypeError:
                pass
            GLib.idle_add(stream.set_state, Gst.State.NULL)
            try:
                self._pipe.remove(stream)
            except Gst.RemoveError:
                logger.debug("Failed to remove stream %s"%stream)
            if stream in self.streams:
                self.streams[self.streams.index(stream)] = None
            event.log_event("playback_track_end", self, current)
            return True
        except AttributeError:
            return True
        except:
            common.log_exception(log=logger)
            return False

    def link_stream(self, stream, track):
        self._pipe.add(stream)
        stream.link(self.adder)
        if not stream.set_track(track):
            logger.error("Failed to start playing \"%s\""%track)
            self.stop()
            return False
        return True

    @common.synchronized
    def _stop(self):
        """
            stop playback
        """
        current = self.current
        self._pipe.set_state(Gst.State.NULL)
        for stream in self.streams:
            self.unlink_stream(stream)
        self._reset_crossfade_timer()
        return current

    @common.synchronized
    def _pause(self):
        self._pipe.set_state(Gst.State.PAUSED)
        self._reset_crossfade_timer()

    @common.synchronized
    def _unpause(self):
        # gstreamer does not buffer paused network streams, so if the user
        # is unpausing a stream, just restart playback
        if not self.current.is_local():
            self._pipe.set_state(Gst.State.READY)

        self._pipe.set_state(Gst.State.PLAYING)
        self._reset_crossfade_timer()

    @common.synchronized
    def seek(self, value):
        """
            seek to the given position in the current stream
        """
        self.streams[self._current_stream].seek(value)
        self._reset_crossfade_timer()

        event.log_event('playback_seeked', self, value)


class AudioStream(Gst.Bin):
    def __init__(self, name, player, caps=None):
        Gst.Bin.__init__(self, name=name)
        self.notify_id = None
        self.track = None
        self._playtime_stamp = None

        self.last_position = 0
        self._settle_flag = 0
        self._settle_trap = 0
        self._seek_event = threading.Event()

        self.caps = caps
        self.setup_elems(player)

    def setup_elems(self, player):
        self.dec = Gst.ElementFactory.make("uridecodebin")
        self.audioconv = Gst.ElementFactory.make("audioconvert")
        self.audioresam = Gst.ElementFactory.make("audioresample")
        self.provided = pipe.ProviderBin(player, "stream_element")
        self.capsfilter = Gst.ElementFactory.make("capsfilter")
        self.capsfilter.set_property("caps", self.caps)
        self.vol = Gst.ElementFactory.make("volume")
        for e in (self.dec, self.audioconv, self.audioresam, self.provided, self.capsfilter, self.vol):
            self.add(e)
        self.audioconv.link(self.audioresam)
        self.audioresam.link(self.capsfilter)
        self.capsfilter.link(self.provided)
        self.provided.link(self.vol)
        self.dec.connect('no-more-pads', self._dec_pad_cb, self.audioconv)

        self.src = Gst.GhostPad.new("src", self.vol.get_static_pad("src"))
        self.add_pad(self.src)

    def _dec_pad_cb(self, dec, v):
        try:
            dec.link(v)
        except:
            pass

    def set_volume(self, vol):
        self.vol.set_property("volume", vol)

    def get_volume(self):
        return self.vol.get_property("volume")

    def get_track(self):
        return self.track

    def set_track(self, track):
        if not track:
            return False
        if track.is_local():
            if not track.exists():
                logger.error("File does not exist: %s" %
                        track.get_loc_for_io())
                return False

        self.track = track

        uri = track.get_loc_for_io()

        logger.info("Playing %s" % uri)
        self.reset_playtime_stamp()

        self.dec.set_property("uri", uri)

        # TODO: abstract this into generic uri handling via providers
        if uri.startswith("cdda://"):
            self.notify_id = self.dec.connect('notify::source',
                    self.__notify_source)

        return True

    def __notify_source(self, *args):
        # this is for handling multiple CD devices properly
        source = self.dec.get_property('source')
        device = self.track.get_loc_for_io().split("#")[-1]
        source.set_property('device', device)
        self.dec.disconnect(self.notify_id)

    def update_playtime(self):
        """
            updates the total playtime for the currently playing track
        """
        if self.track and self._playtime_stamp:
            last = self.track.get_tag_raw('__playtime')
            if type(last) == str:
                try:
                    last = int(last)
                except:
                    last = 0
            elif type(last) != int:
                last = 0
            self.track.set_tag_raw('__playtime',
                    last + int(time.time() - self._playtime_stamp) )
            self._playtime_stamp = None

    def reset_playtime_stamp(self):
        self._playtime_stamp = int(time.time())

    def set_state(self, state):
        logger.debug("Setting state on %s %s"%(self.get_name(), state))
        self._settle_flag = 0
        if state == Gst.State.PLAYING:
            Gst.Bin.set_state(self, state)
            self._settle_state()
            self.reset_playtime_stamp()
        elif state == Gst.State.PAUSED:
            self.update_playtime()
            Gst.Bin.set_state(self, state)
            self.reset_playtime_stamp()
        else:
            self.update_playtime()
            Gst.Bin.set_state(self, state)

    def _get_gst_state(self):
        """
            Returns the raw GStreamer state
        """
        return self.get_state(timeout=50*Gst.MSECOND)[1]

    def is_playing(self):
        """
            Returns True if the player is currently playing
        """
        return self._get_gst_state() == Gst.State.PLAYING

    def is_paused(self):
        """
            Returns True if the player is currently paused
        """
        return self._get_gst_state() == Gst.State.PAUSED

    def get_current(self):
        if self.is_playing() or self.is_paused():
            return self.track
        else:
            return None

    def get_position(self):
        if self.is_paused():
            return self.last_position
        
        res, self.last_position = self.dec.query_position(Gst.Format.TIME)
        if not res:
            #common.log_exception(logger)
            self.last_position = 0
        return self.last_position

    def _settle_state(self):
        self._settle_flag = 1
        if self._settle_trap > 10:
            self._settle_trap = 0
            self._settle_flag = 0
            logger.debug("Failed to settle state on %s."%self)
            Gst.Bin.set_state(self, Gst.State.NULL)
            event.log_event("stream_settled", self, None)
            return
        GLib.idle_add(self._settle_state_sub)

    @common.threaded
    def _settle_state_sub(self):
        """
            hack to reset gstreamer states.
            TODO: find a cleaner way of doing this.
        """
        if self._settle_flag == 1 and self._get_gst_state() == Gst.State.PAUSED:
            self._settle_trap += 1
            logger.debug("Settling state on %s."%repr(self))
            self.set_state(Gst.State.PLAYING)
        else:
            self._settle_flag = 0
            self._settle_trap = 0
            event.log_event("stream_settled", self, None)

    def seek(self, value):
        """
            seek to the given position in the current stream
        """
        if self._settle_flag == 1:
            event.add_callback(self._seek_delayed, "stream_settled", self)
            self._seek_event.clear()
            self._seek_event.wait()

        value = int(Gst.SECOND * value)
        seekevent = Gst.Event.new_seek(1.0, Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,Gst.SeekType.SET, value,
            Gst.SeekType.NONE, 0)

        self.vol.send_event(seekevent)
        # update this in case we're paused
        self.last_position = value

    def _seek_delayed(self, type, object, value):
        """
            internal code used if seek is called before the stream is ready
        """
        if self._settle_flag == 1 or object != self:
            return
        event.remove_callback(self._seek_delayed, type, object)
        self._seek_event.set()

