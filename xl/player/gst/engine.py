# Copyright (C) 2008-2010 Adam Olsen
# Copyright (C) 2014-2015 Dustin Spicuzza
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

from gi.repository import GLib
from gi.repository import Gst

import logging
import os
import urllib.parse

from xl import common
from xl import event

from xl.nls import gettext as _

from . import gst_utils
from .dynamic_sink import DynamicAudioSink
from .sink import create_device, priority_boost

from xl.player.engine import ExaileEngine
from xl.player.track_fader import TrackFader
from xl.player.gst import missing_plugin


logger = logging.getLogger(__name__)


class ExaileGstEngine(ExaileEngine):
    """
    Super shiny GStreamer-based engine that does all the things!

    * Audio plugins to modify the output stream
    * gapless playback
    * crossfading (requires gst-plugins-bad)
    * Dynamic audio device switching at runtime

    Notes about crossfading:

    The big change from previous attempts at crossfading is that unlike
    the former unified engine, this tries to depend solely on the playbin
    element to play audio files. The reason for this is that playbin
    is 5000+ lines of battle-hardened C code that handles all of the
    weird edges cases in gstreamer, and we don't wish to duplicate that in
    Exaile if we can avoid it.

    Instead, we can use multiple playbin instances that have duplicate
    output audio devices. This makes crossfading a significantly simpler
    proposition.

    There are two modes for this thing:

    * One is normal/gapless mode (no crossfade), and it uses a normal
      playbin element and controls that directly. The playbin is wrapped
      by the AudioStream object, and it's audio sink is a DynamicAudioSink
      element with the

    * The other is crossfading mode (which requires gst-plugins-bad to be
      installed). Create multiple AudioStream objects, and they have a
      DynamicAudioSink object hooked up to an interaudiosink.

    You can register plugins to modify the output audio via the following
    providers:

    * gst_audio_filter: Multiple instances of this can be created, as they
                        get applied to each stream. It is recommended that
                        plugins inherit from :class:`.ElementBin`
    """

    def __init__(self, name, player, disable_autoswitch):
        ExaileEngine.__init__(self, name, player)
        self.logger = logging.getLogger('%s [%s]' % (__name__, name))

        # Default settings
        self.crossfade_enabled = False
        self.crossfade_duration = 3000

        self.audiosink_device = None
        self.audiosink = None
        self.custom_sink_pipe = None

        # If True, then playback will be stopped if the audio sink changes without
        # the user asking for it
        self.disable_autoswitch = disable_autoswitch

        # This means to fade in when the user plays a track, only enabled
        # when crossfade isn't enabled
        self.user_fade_enabled = False
        self.user_fade_duration = 1000

        # Key: option name; value: attribute on self
        options = {
            '%s/crossfading' % self.name: 'crossfade_enabled',
            '%s/crossfade_duration' % self.name: 'crossfade_duration',
            '%s/audiosink_device' % self.name: 'audiosink_device',
            '%s/audiosink' % self.name: 'audiosink',
            '%s/custom_sink_pipe' % self.name: 'custom_sink_pipe',
            '%s/user_fade_enabled' % self.name: 'user_fade_enabled',
            '%s/user_fade' % self.name: 'user_fade_duration',
        }

        self.settings_unsubscribe = common.subscribe_for_settings(
            self.name, options, self
        )

    #
    # Dynamic properties
    #

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

        if not getattr(self, 'initialized', False):
            return

        if name in ['crossfade_enabled', 'crossfade_duration']:
            self._reconfigure_crossfader()

        if name in ['audiosink_device', 'audiosink', 'custom_sink_pipe']:
            self._reconfigure_sink()

    #
    # API
    #

    def initialize(self):

        object.__setattr__(self, 'initialized', True)

        self.main_stream = AudioStream(self)
        self.other_stream = None
        self.crossfade_out = None

        self.player.engine_load_volume()

        self._reconfigure_crossfader()

    def _reconfigure_crossfader(self):

        self.logger.info("Reconfiguring crossfading")

        cf_duration = None
        if self.crossfade_enabled:
            cf_duration = self.crossfade_duration / 1000.0

            if self.other_stream is None:
                self.other_stream = AudioStream(self)
                self.other_stream.set_user_volume(self.main_stream.get_user_volume())

            self.other_stream.reconfigure_fader(cf_duration, cf_duration)
            self.logger.info("Crossfade: enabled (%sms)", self.crossfade_duration)
        else:
            self.logger.info("Crossfade: disabled")
            if self.other_stream is not None:
                self.other_stream.destroy()

        self.main_stream.reconfigure_fader(cf_duration, cf_duration)

    def _reconfigure_sink(self):

        self.logger.info("Reconfiguring audiosinks")

        self.main_stream.reconfigure_sink()
        if self.other_stream is not None:
            self.other_stream.reconfigure_sink()

    def destroy(self, permanent=True):
        self.main_stream.destroy()

        if self.other_stream is not None:
            self.other_stream.destroy()

        if permanent:
            self.settings_unsubscribe()

        object.__setattr__(self, 'initialized', False)

        self.needs_sink = True
        self.audiosink = None
        self.audiosink_device = None

    #
    # Engine API
    #

    def get_current_track(self):
        return self.main_stream.current_track

    def get_position(self):
        return self.main_stream.get_position()

    def get_state(self):
        state = self.main_stream.get_gst_state()
        if state == Gst.State.PLAYING:
            return 'playing'
        elif state == Gst.State.PAUSED:
            return 'paused'
        else:
            return 'stopped'

    def get_volume(self):
        return self.main_stream.get_user_volume()

    def on_track_stopoffset_changed(self, track):

        for stream in [self.main_stream, self.other_stream]:

            if stream is None or stream.current_track != track:
                continue

            # The fader executes the stop offset, so reconfigure it

            if self.crossfade_enabled:
                stream.reconfigure_fader(
                    self.crossfade_duration, self.crossfade_duration
                )
            else:
                stream.reconfigure_fader(None, None)

    def pause(self):
        self.main_stream.pause()

        if self.other_stream is not None:
            self.other_stream.stop()

    def play(self, track, start_at, paused):
        self._next_track(track, start_at, paused, False, False)

    def seek(self, value):
        return self.main_stream.seek(value)

    def set_volume(self, volume):
        self.main_stream.set_user_volume(volume)
        if self.other_stream is not None:
            self.other_stream.set_user_volume(volume)

    def stop(self):
        if self.other_stream is not None:
            self.other_stream.stop()

        prior_track = self.main_stream.stop(emit_eos=False)
        self.player.engine_notify_track_end(prior_track, True)

    def unpause(self):
        self.main_stream.unpause()

    #
    # Engine private functions
    #

    def _autoadvance_track(self, still_fading=False):

        track = self.player.engine_autoadvance_get_next_track()

        if track:
            play_args = self.player.engine_autoadvance_notify_next(track) + (
                False,
                True,
            )
            self._next_track(*play_args)

        # If still fading, don't stop
        elif not still_fading:
            self.stop()

    @common.idle_add()
    def _eos_func(self, stream):

        if stream == self.main_stream:
            self._autoadvance_track()

    def _error_func(self, stream, msg):
        # Destroy the streams, and create a new one, just in case

        self.player.engine_notify_error(msg)
        self.destroy(permanent=False)
        self.initialize()

    def _next_track(self, track, start_at, paused, already_queued, autoadvance):

        prior_track = self.main_stream.current_track

        # Notify that the track is done
        if prior_track is not None:
            self.player.engine_notify_track_end(prior_track, False)

        if self.crossfade_enabled:
            self.main_stream, self.other_stream = self.other_stream, self.main_stream
            self.main_stream.play(
                track,
                start_at,
                paused,
                already_queued,
                self.crossfade_duration / 1000.0,
                self.crossfade_duration / 1000.0,
            )
            self.other_stream.fader.fade_out_on_play()
        elif self.user_fade_enabled and not autoadvance:
            self.main_stream.play(
                track,
                start_at,
                paused,
                already_queued,
                self.user_fade_duration / 1000.0,
            )
        else:
            self.main_stream.play(track, start_at, paused, already_queued)

        self.player.engine_notify_track_start(track)


class AudioStream:
    """
    An object that can play one or more tracks
    """

    idx = 0

    def __init__(self, engine):

        AudioStream.idx += 1
        self.name = '%s-audiostream-%s' % (engine.name, self.idx)
        self.engine = engine

        self.logger = logging.getLogger(
            '%s [%s-a%s]' % (__name__, engine.name, self.idx)
        )

        #  track being played by this stream
        self.current_track = None
        self.buffered_track = None

        # This exists because if there is a sink error, it doesn't
        # really make sense to recreate the sink -- it'll just fail
        # again. Instead, wait for the user to try to play a track,
        # and maybe the issue has resolved itself (plugged device in?)
        self.needs_sink = True
        self.last_position = 0

        self.audio_filters = gst_utils.ProviderBin(
            'gst_audio_filter', '%s-filters' % self.name
        )

        self.playbin = Gst.ElementFactory.make("playbin", "%s-playbin" % self.name)
        if self.playbin is None:
            raise TypeError("gstreamer 1.x base plugins not installed!")

        gst_utils.disable_video_text(self.playbin)

        self.playbin.connect("about-to-finish", self.on_about_to_finish)

        video = Gst.ElementFactory.make("fakesink", '%s-fakevideo' % self.name)
        video.set_property('sync', True)
        self.playbin.set_property('video-sink', video)

        self.audio_sink = DynamicAudioSink('%s-sink' % self.name)
        self.playbin.set_property('audio-sink', self.audio_sink)

        # Setup the bus
        bus = self.playbin.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

        # priority boost hack if needed
        priority_boost(self.playbin)

        # Pulsesink changes volume behind our back, track it
        self.playbin.connect('notify::volume', self.on_volume_change)

        self.fader = TrackFader(
            self, self.on_fade_out_begin, '%s-fade-%s' % (engine.name, self.idx)
        )

    def destroy(self):

        self.fader.stop()
        self.playbin.set_state(Gst.State.NULL)
        self.playbin.get_bus().remove_signal_watch()

    def reconfigure_sink(self):
        self.needs_sink = False
        sink = create_device(self.engine.name)

        # Works for pulsesink, but not other sinks
        # -> Not a perfect solution, still some audio blip is heard. Unfortunately,
        #    can't do better without direct support from gstreamer
        if self.engine.disable_autoswitch and hasattr(sink.props, 'current_device'):
            self.selected_sink = sink.props.device
            sink.connect('notify::current-device', self._on_sink_change_notify)

        self.audio_sink.reconfigure(sink)

    def _on_sink_change_notify(self, sink, param):
        if self.selected_sink != sink.props.current_device:
            domain = GLib.quark_from_string("g-exaile-error")
            err = GLib.Error.new_literal(domain, "Audio device disconnected", 0)
            self.playbin.get_bus().post(
                Gst.Message.new_error(None, err, "Disconnected")
            )
            self.logger.info("Detected device disconnect, stopping playback")

    def reconfigure_fader(self, fade_in_duration, fade_out_duration):
        if self.get_gst_state() != Gst.State.NULL:
            self.fader.setup_track(
                self.current_track, fade_in_duration, fade_out_duration, is_update=True
            )

    def get_gst_state(self):
        return self.playbin.get_state(timeout=50 * Gst.MSECOND)[1]

    def get_position(self):
        # TODO: This only works when pipeline is prerolled/ready?
        if not self.get_gst_state() == Gst.State.PAUSED:
            res, self.last_position = self.playbin.query_position(Gst.Format.TIME)

            if res is False:
                self.last_position = 0

        return self.last_position

    def get_volume(self):
        return self.playbin.props.volume

    def get_user_volume(self):
        return self.fader.get_user_volume()

    def pause(self):
        # This caches the current last position before pausing
        self.get_position()
        self.playbin.set_state(Gst.State.PAUSED)
        self.fader.pause()

    def play(
        self,
        track,
        start_at,
        paused,
        already_queued,
        fade_in_duration=None,
        fade_out_duration=None,
    ):
        '''fade duration is in seconds'''

        if not already_queued:
            self.stop(emit_eos=False)

            # For the moment, the only safe time to add/remove elements
            # is when the playbin is NULL, so do that here..
            if self.audio_filters.setup_elements():
                self.logger.debug("Applying audio filters")
                self.playbin.props.audio_filter = self.audio_filters
            else:
                self.logger.debug("Not applying audio filters")
                self.playbin.props.audio_filter = None

        if self.needs_sink:
            self.reconfigure_sink()

        self.current_track = track
        self.last_position = 0
        self.buffered_track = None

        uri = track.get_loc_for_io()
        self.logger.info("Playing %s", common.sanitize_url(uri))

        # This is only set for gapless playback
        if not already_queued:
            self.playbin.set_property("uri", uri)
            if urllib.parse.urlsplit(uri)[0] == "cdda":
                self.notify_id = self.playbin.connect(
                    'source-setup', self.on_source_setup, track
                )

        # Start in paused mode if we need to seek
        if paused or start_at is not None:
            self.playbin.set_state(Gst.State.PAUSED)
        elif not already_queued:
            self.playbin.set_state(Gst.State.PLAYING)

        self.fader.setup_track(track, fade_in_duration, fade_out_duration, now=0)

        if start_at is not None:
            self.seek(start_at)
            if not paused:
                self.playbin.set_state(Gst.State.PLAYING)

        if paused:
            self.fader.pause()

    def seek(self, value):
        '''value is in seconds'''

        # TODO: Make sure that we're in a valid seekable state before seeking?

        # wait up to 1s for the state to switch, else this fails
        if (
            self.playbin.get_state(timeout=1000 * Gst.MSECOND)[0]
            != Gst.StateChangeReturn.SUCCESS
        ):
            # TODO: This error message is misleading, when does this ever happen?
            # TODO: if the sink is incorrectly specified, this error happens first.
            # self.engine._error_func(self, "Could not start at specified offset")
            self.logger.warning("Error seeking to specified offset")
            return False

        new_position = int(Gst.SECOND * value)
        seek_event = Gst.Event.new_seek(
            1.0,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            new_position,
            Gst.SeekType.NONE,
            0,
        )

        self.last_position = new_position
        self.fader.seek(value)

        return self.playbin.send_event(seek_event)

    def set_volume(self, volume):
        # self.logger.debug("Set playbin volume: %.2f", volume)
        # TODO: strange issue where pulse sets the system audio volume
        #       when exaile starts up...
        self.playbin.props.volume = volume

    def set_user_volume(self, volume):
        self.logger.debug("Set user volume: %.2f", volume)
        self.fader.set_user_volume(volume)

    def stop(self, emit_eos=True):
        prior_track = self.current_track
        self.current_track = None
        self.playbin.set_state(Gst.State.NULL)
        self.fader.stop()

        if emit_eos:
            self.engine._eos_func(self)

        return prior_track

    def unpause(self):

        # gstreamer does not buffer paused network streams, so if the user
        # is unpausing a stream, just restart playback
        current = self.current_track
        if not (current.is_local() or current.get_tag_raw('__length')):
            self.playbin.set_state(Gst.State.READY)

        self.playbin.set_state(Gst.State.PLAYING)
        self.fader.unpause()

    #
    # Events
    #

    def on_about_to_finish(self, *args):
        """
        This function exists solely to allow gapless playback for audio
        formats that support it. Setting the URI property of the playbin
        will queue the track for playback immediately after the previous
        track.

        .. note:: This is called from the gstreamer thread
        """

        if self.engine.crossfade_enabled:
            return

        track = self.engine.player.engine_autoadvance_get_next_track(gapless=True)
        if track:
            uri = track.get_loc_for_io()
            self.playbin.set_property('uri', uri)
            self.buffered_track = track

            self.logger.debug(
                "Gapless transition: queuing %s", common.sanitize_url(uri)
            )

    def on_fade_out_begin(self):

        if self.engine.crossfade_enabled:
            self.engine._autoadvance_track(still_fading=True)

    def on_message(self, bus, message):
        """
        This is called on the main thread
        """

        if message.type == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            if not percent < 100:
                self.logger.info('Buffering complete')
            if percent % 5 == 0:
                event.log_event('playback_buffering', self.engine.player, percent)

        elif message.type == Gst.MessageType.TAG:
            """Update track length and optionally metadata from gstreamer's parser.
            Useful for streams and files mutagen doesn't understand."""

            current = self.current_track

            if not current.is_local():
                gst_utils.parse_stream_tags(current, message.parse_tag())

            if current and not current.get_tag_raw('__length'):
                res, raw_duration = self.playbin.query_duration(Gst.Format.TIME)
                if not res:
                    self.logger.error("Couldn't query duration")
                    raw_duration = 0
                duration = float(raw_duration) / Gst.SECOND
                if duration > 0:
                    current.set_tag_raw('__length', duration)

        elif (
            message.type == Gst.MessageType.EOS
            and not self.get_gst_state() == Gst.State.PAUSED
        ):
            self.engine._eos_func(self)

        elif (
            message.type == Gst.MessageType.STREAM_START
            and message.src == self.playbin
            and self.buffered_track is not None
        ):

            # This handles starting the next track during gapless transition
            buffered_track = self.buffered_track
            self.buffered_track = None
            play_args = self.engine.player.engine_autoadvance_notify_next(
                buffered_track
            ) + (True, True)
            self.engine._next_track(*play_args)

        elif message.type == Gst.MessageType.STATE_CHANGED:

            # This idea from quodlibet: pulsesink will not notify us when
            # volume changes if the stream is paused, so do it when the
            # state changes.
            if message.src == self.audio_sink:
                self.playbin.notify("volume")

        elif message.type == Gst.MessageType.ERROR:
            self.__handle_error_message(message)

        elif message.type == Gst.MessageType.ELEMENT:
            if not missing_plugin.handle_message(message, self.engine):
                logger.debug(
                    "Unexpected element-specific GstMessage received from %s: %s",
                    message.src,
                    message,
                )

        elif message.type == Gst.MessageType.WARNING:
            # TODO there might be some useful warnings we ignore for now.
            gerror, debug_text = Gst.Message.parse_warning(message)
            logger.warning(
                "Unhandled GStreamer warning received:\n\tGError: %s\n\tDebug text: %s",
                gerror,
                debug_text,
            )

        else:
            # TODO there might be some useful messages we ignore for now.
            logger.debug(
                "Unhandled GstMessage of type %s received: %s", message.type, message
            )

    def __handle_error_message(self, message):
        # Error handling code is from quodlibet
        gerror, debug_info = message.parse_error()
        message_text = ""
        if gerror:
            message_text = gerror.message.rstrip(".")

        if message_text == "":
            # The most readable part is always the last..
            message_text = debug_info[debug_info.rfind(':') + 1 :]

            # .. unless there's nothing in it.
            if ' ' not in message_text:
                if debug_info.startswith('playsink'):
                    message_text += _(
                        ': Possible audio device error, is it plugged in?'
                    )

        self.logger.error("Playback error: %s", message_text)
        self.logger.debug("- Extra error info: %s", debug_info)

        envname = 'GST_DEBUG_DUMP_DOT_DIR'
        if envname not in os.environ:
            import xl.xdg

            os.environ[envname] = xl.xdg.get_logs_dir()

        Gst.debug_bin_to_dot_file(self.playbin, Gst.DebugGraphDetails.ALL, self.name)
        self.logger.debug(
            "- Pipeline debug info written to file '%s/%s.dot'",
            os.environ[envname],
            self.name,
        )

        self.engine._error_func(self, message_text)

    def on_source_setup(self, playbin, source, track):
        # this is for handling multiple CD devices properly
        device = track.get_loc_for_io().split("#")[-1]
        source.props.device = device
        playbin.disconnect(self.notify_id)

    def on_volume_change(self, e, p):
        real = self.playbin.props.volume
        vol, is_same = self.fader.calculate_user_volume(real)
        if not is_same:
            GLib.idle_add(self.engine.player.engine_notify_user_volume_change, vol)
