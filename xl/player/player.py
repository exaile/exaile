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


import time

from gi.repository import GLib

from xl import common
from xl import event
from xl import settings

import logging

logger = logging.getLogger(__name__)


class ExailePlayer:
    """
    This is the player object that everything in Exaile interacts with
    to control audio playback. The player object controls a playback
    engine, which actually controls audio playback. Nothing in this
    object should be specific to a particular engine. Examples of engines
    could be GStreamer, Xine, etc. Currently only the GStreamer engine
    is actually implemented.

    All public functions are assumed to be called from the Glib main
    thread, or bad things will happen. This includes most engine functions,
    with one or two noted exceptions.
    """

    def __init__(self, name, disable_autoswitch=False):
        self.queue = None
        self._name = name

        self._playtime_stamp = None

        self._delay_id = None
        self._stop_id = None
        self._engine = None

        self._auto_advance_delay = 0
        self._auto_advance = True
        self._gapless_enabled = True
        self.__volume = 1.0

        options = {
            '%s/auto_advance_delay' % name: '_auto_advance_delay',
            '%s/auto_advance' % name: '_auto_advance',
            '%s/gapless_playback' % name: '_gapless_enabled',
            '%s/volume' % name: '_volume',
        }

        self._settings_unsub = common.subscribe_for_settings(name, options, self)

        self._setup_engine(disable_autoswitch)

        event.add_callback(self._on_track_end, 'playback_track_end', self)
        event.add_callback(self._on_track_tags_changed, 'track_tags_changed')

    def _setup_engine(self, disable_autoswitch):

        if self._engine is not None:
            self._engine.destroy()

        # allows building docs
        engine_name = settings.get_option("player/engine", "normal")

        if engine_name == 'rtfd_hack':
            return None

        # TODO: support other engines
        from .gst.engine import ExaileGstEngine

        self._engine = ExaileGstEngine(self._name, self, disable_autoswitch)
        self._engine.initialize()

    @property
    def _volume(self):
        return self.__volume

    @_volume.setter
    def _volume(self, value):
        self.__volume = value
        if self._engine is not None:
            self.engine_load_volume()

    def _on_track_end(self, name, obj, track):
        if not track:
            return
        try:
            i = int(track.get_tag_raw('__playcount'))
        except Exception:
            i = 0
        track.set_tags(__playcount=i + 1, __last_played=time.time())

    @common.idle_add()
    def _on_track_tags_changed(self, eventtype, track, tags):
        if '__stopoffset' in tags:
            self._engine.on_track_stopoffset_changed(track)

    def destroy(self):
        """
        Destroys the engine and other resources for this player object.
        Unless you own the object, you probably should never call this.
        """
        if self._settings_unsub is not None:
            self._settings_unsub()
            self._settings_unsub = None

        if self._engine is not None:
            self._engine.destroy()
            self._engine = None

    def get_volume(self):
        """
        Gets the current user volume

        :returns: the volume percentage
        :type: int
        """
        return self._volume * 100

    def set_volume(self, volume):
        """
        Sets the current user volume

        :param volume: the volume percentage
        :type volume: int
        """
        volume = common.clamp(volume, 0, 100)
        settings.set_option("%s/volume" % self._name, volume / 100)

    def modify_volume(self, diff):
        """
        Changes the current user volume

        :param diff: the volume difference (pos or neg) percentage units
        :type volume: int
        """
        v = self.get_volume()
        self.set_volume(v + diff)

    @property
    def current(self):
        return self._engine.get_current_track()

    def play(self, track, start_at=None, paused=False):
        """
        Starts the playback with the provided track
        or stops the playback it immediately if none

        :param track: the track to play or None
        :type track: :class:`xl.trax.Track`
        :param start_at: The offset to start playback at, in seconds
        :param paused: If True, start the track in 'paused' mode

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `playback_player_start`: indicates the start of playback overall
            * `playback_track_start`: indicates playback start of a track
        """
        if track is None:
            self.stop()
        else:
            if self.is_stopped():
                event.log_event('playback_player_start', self, track)

            play_args = self._get_play_params(track, start_at, paused, False)
            self._engine.play(*play_args)
            if play_args[2]:
                event.log_event('playback_player_pause', self, track)
                event.log_event("playback_toggle_pause", self, track)

    def stop(self):
        """
        Stops the playback

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `playback_player_end`: indicates the end of playback overall
            * `playback_track_end`: indicates playback end of a track
        """
        state = self.get_state()

        if state == 'playing' or state == 'paused':

            self._engine.stop()
            return True
        else:
            logger.debug("Stop ignored when state == %s", state)

        return False

    def pause(self):
        """
        Pauses the playback if playing, does not toggle it

        :returns: True if paused, False otherwise

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `playback_player_pause`: indicates that the playback has been paused
            * `playback_toggle_pause`: indicates that the playback has been paused or resumed
        """
        self._cancel_delayed_start()
        if self.is_playing():

            current = self.current
            self._update_playtime(current)
            self._engine.pause()
            self._reset_playtime_stamp()

            event.log_event('playback_player_pause', self, current)
            event.log_event("playback_toggle_pause", self, current)
            return True

        return False

    def unpause(self):
        """
        Resumes the playback if it is paused, does not toggle it

        :returns: True if paused, False otherwise

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `playback_player_resume`: indicates that the playback has been resumed
            * `playback_toggle_pause`: indicates that the playback has been paused or resumed
        """
        self._cancel_delayed_start()
        if self.is_paused():

            self._reset_playtime_stamp()
            self._engine.unpause()

            current = self.current
            event.log_event('playback_player_resume', self, current)
            event.log_event("playback_toggle_pause", self, current)
            return True
        return False

    def toggle_pause(self):
        """
        Toggles between playing and paused state. Only valid when playback
        is not stopped.

        :returns: True if toggled, false otherwise

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `playback_toggle_pause`: indicates that the playback has been paused or resumed
        """
        state = self.get_state()
        if state == 'paused':
            return self.unpause()
        elif state == 'playing':
            return self.pause()
        else:
            return False

    def seek(self, value):
        """
        Seek to a position in the currently playing stream

        :param value: the position in seconds
        :type value: int
        """
        if self._engine.seek(value):
            event.log_event('playback_seeked', self, value)

    def get_position(self):
        """
        Gets the current playback position of the playing track

        :returns: the playback position in nanoseconds
        :rtype: int
        """
        return self._engine.get_position()

    def get_time(self):
        """
        Gets the current playback time

        :returns: the playback time in seconds
        :rtype: float
        """
        return self.get_position() / 1e9

    def get_progress(self) -> float:
        """
        Gets the current playback progress

        :returns: the playback progress as [0..1]
        """
        try:
            progress = self.get_time() / self.current.get_tag_raw("__length")
        except TypeError:  # track doesn't have duration info
            progress = 0
        except AttributeError:  # no current track
            progress = 0
        else:
            if progress < 0:
                progress = 0
            elif progress > 1:
                progress = 1
        return progress

    def set_progress(self, progress):
        """
        Seeks to the progress position

        :param progress: value ranged at [0..1]
        :type progress: float
        """
        seek_position = 0

        try:
            length = self.current.get_tag_raw('__length')
            seek_position = length * progress
        except (TypeError, AttributeError):
            pass

        self.seek(seek_position)

    def modify_time(self, diff):
        """
        Modifies the current position backwards or forwards.

        If position ends up after the end or before the start of the track
        it is truncated to lay inside the track.

        :param diff: value in seconds
        :type diff: int
        """
        try:
            length = self.current.get_tag_raw('__length')
        except (TypeError, AttributeError):
            return

        if length is None:
            return

        pos = self.get_time()
        seek_pos = pos + diff

        # Make sure we don't seek outside the current track. Subtract a little
        # from length, player seems to hang sometimes if we seek to the end of
        # a track.
        seek_pos = max(0, min(seek_pos, length - 2))

        self.seek(seek_pos)

    def get_state(self):
        """
        Gets the player state

        :returns: one of *playing*, *paused* or *stopped*
        :rtype: string
        """
        return self._engine.get_state()

    def is_playing(self):
        """
        Convenience method to find out if the player is currently playing

        :returns: whether the player is currently playing
        :rtype: bool
        """
        return self._engine.get_state() == 'playing'

    def is_paused(self):
        """
        Convenience method to find out if the player is currently paused

        :returns: whether the player is currently paused
        :rtype: bool
        """
        return self._engine.get_state() == 'paused'

    def is_stopped(self):
        """
        Convenience method to find out if the player is currently stopped

        :returns: whether the player is currently stopped
        :rtype: bool
        """
        return self._engine.get_state() == 'stopped'

    #
    # Engine-only API
    #

    def engine_load_volume(self):
        """
        Load volume from settings, this function will call set_volume
        on the engine

        .. note:: Only to be called from engine
        """
        self._engine.set_volume(self._volume)

    def engine_notify_user_volume_change(self, vol):
        """
        Engine calls this when something inside the engine changes
        the user volume.

        .. note:: Only to be called from engine
        """
        settings.set_option('%s/volume' % self._name, vol)

    def engine_notify_track_start(self, track):
        """
        Called when a track has just entered the playing state

        :param track: Track that is being played now

        .. note:: Only to be called from engine
        """

        self._reset_playtime_stamp()
        event.log_event('playback_track_start', self, track)

    def engine_notify_track_end(self, track, done):
        """
        Called when a track has been stopped. Either:

        - stop() was called
        - play() was called and the prior track was stopped

        :param track: Must be the track that was just playing, and must
                      never be None

        :param done:  If True, no further tracks will be played

        .. note:: Only to be called from engine
        """

        self._update_playtime(track)
        event.log_event('playback_track_end', self, track)

        if done:
            self._cancel_delayed_start()
            event.log_event('playback_player_end', self, track)

    @common.idle_add()
    def engine_notify_error(self, msg):
        """
        Notification that some kind of error has occurred. If the error
        is not recoverable, the engine is expected to stop playback and
        reset itself to a state where playback can begin again.

        .. note:: Only to be called from engine
        """
        event.log_event('playback_error', self, msg)

    def engine_autoadvance_get_next_track(self, gapless=False):
        """
        Engine calls this when it wants to see what the next track
        to play is. The track may or may not actually get played.
        If the track gets played, then the engine must call
        engine_autoadvance_notify_next, engine_notify_playback_stop,
        and engine_notify_playback_start

        May be called on another thread.

        :param gapless: Set to True if the autoadvance is part of a gapless
                        playback attempt

        :returns: The next track, or None if the engine should not try
                  to play another track immediately

        .. note:: Only to be called from engine
        """

        if not self._auto_advance:
            return

        if gapless:
            if self._auto_advance_delay != 0 or not self._gapless_enabled:
                return

        return self.queue.get_next()

    def engine_autoadvance_notify_next(self, track):
        """
        Engine calls this when it has started playing the next track as
        part of an auto advance action.

        :param track: The track that will be played

        :returns: (track, start_at, paused) parameters that can be passed
                  to the 'play' function of the engine.

        .. note:: Only to be called from engine
        """

        self.queue.next(autoplay=False)

        return self._get_play_params(track, None, False, True)

    #
    # Playtime related stuffs
    #

    def _get_play_params(self, track, start_at, paused, autoadvance):
        if start_at is None or start_at <= 0:
            start_at = None
            start_offset = track.get_tag_raw('__startoffset') or 0
            if start_offset > 0:
                start_at = start_offset

        # Once playback has started, if there's a delay, pause the stream
        # for delay number of seconds
        self._cancel_delayed_start()

        if not paused and autoadvance and self._auto_advance_delay > 0:
            delay = int(self._auto_advance_delay)
            logger.debug("Delaying start for %sms", delay)
            self._delay_id = GLib.timeout_add(delay, self._delayed_start)
            paused = True

        return track, start_at, paused

    def _delayed_start(self):
        logger.debug("Resuming playback after delayed start")
        self.unpause()

    def _update_playtime(self, track):
        """
        updates the total playtime for the currently playing track

        .. should be called whenever a pause/stop event occurs
        """
        if track and self._playtime_stamp:
            last = track.get_tag_raw('__playtime')
            if isinstance(last, str):
                try:
                    last = int(last)
                except Exception:
                    last = 0
            elif not isinstance(last, int):
                last = 0
            track.set_tag_raw(
                '__playtime', last + int(time.time() - self._playtime_stamp)
            )
            self._playtime_stamp = None

    def _reset_playtime_stamp(self):
        self._playtime_stamp = int(time.time())

    #
    # Delayed start stuff
    #

    def _cancel_delayed_start(self):
        if self._delay_id is not None:
            GLib.source_remove(self._delay_id)
            self._delay_id = None
