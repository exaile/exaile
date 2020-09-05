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


class ExaileEngine:
    """
    Interface that the ExailePlayer uses to control the engines. Other
    parts of Exaile should never interact directly with the engines, but
    interact with the ExailePlayer instead.

    Engines should not call play/stop/pause/unpause on itself directly,
    should call through the player object instead.

    All public functions are assumed to be called from the Glib main
    thread, or bad things will happen.

    The ExailePlayer object provides a common API that engines must use
    to indicate the current playback status, or retrieve things such as
    the next track to be played.

    Player API: Playback status:

    * engine_notify_track_start: Called when a track begins playback
    * engine_notify_track_end: Called when a track has stopped playing
    * engine_notify_error: Call this to notify the user of an error

    Player API: Auto-advance

    * engine_autoadvance_get_next_track: Call this to determine whether
      a new track should be played after the current track
    * engine_autoadvance_notify_next: Call when the auto advance track is
      actually played.

    Player API: misc

    * engine_notify_user_volume_change: Call this when something inside
      of the engine causes the user volume to change.

    Engines are expected to honor the value of the __startoffset and
    __stopoffset flags to start/stop tracks at the appropriate offsets.
    """

    def __init__(self, name, player):
        self.name = name
        self.player = player

    def initialize(self):
        """
        Initialize the engine.

        The engine should call `player.engine_load_volume` when
        initialization has been completed.
        """
        raise NotImplementedError

    def destroy(self):
        """
        Closes all resources associated with this engine
        """
        raise NotImplementedError

    def get_current_track(self):
        """
        :returns: the current track that is playing, or None
        """
        raise NotImplementedError

    def get_position(self):
        """
        Gets the current playback position of the playing track

        :returns: the playback position in nanoseconds
        :rtype: int
        """
        raise NotImplementedError

    def get_state(self):
        """
        Gets the player state

        :returns: one of *playing*, *paused* or *stopped*
        :rtype: string
        """
        raise NotImplementedError

    def get_volume(self):
        """
        Gets the current engine volume

        :returns: the volume percentage (0..1)
        :type: float
        """
        raise NotImplementedError

    def on_track_stopoffset_changed(self, track):
        """
        Called when the stop offset of a track has been changed by the
        user. Engines should adjust the playing time of the track.
        """

    def pause(self):
        """
        Pauses the playback, does not toggle it
        """
        raise NotImplementedError

    def play(self, track, start_at, paused):
        """
        Starts the playback with the provided track or stops the playback
        immediately if none. If the __startoffset tag is set, then
        start_at will be set to that value.

        Calls self.player.engine_notify_track_end if a prior track was playing.

        Calls self.player.engine_notify_track_start when the track has started.

        :param track: the track to play
        :type track: :class:`xl.trax.Track`
        :param start_at: The offset to start playback at, in seconds; or None
        :param paused: If True, start the track in 'paused' mode
        """
        raise NotImplementedError

    def seek(self, value):
        """
        Seek to a position in the currently playing stream

        :param value: the position in seconds
        :type value: float
        """
        raise NotImplementedError

    def set_volume(self, volume):
        """
        Sets the volume on this engine

        :param volume: the volume percentage (0..1)
        :type volume: float
        """
        raise NotImplementedError

    def stop(self):
        """
        Stops playback, and calls self.player.engine_notify_track_end
        """
        raise NotImplementedError

    def unpause(self):
        """
        Unpauses the playback, does not toggle it
        """
        raise NotImplementedError
