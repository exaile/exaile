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
import pickle

from xl import common, event, playlist, settings

logger = logging.getLogger(__name__)


class PlayQueue(playlist.Playlist):
    """
    Manages the queue of songs to be played

    The content of the queue are processed before processing
    the content of the assigned playlist.

    When the remove_item_when_played option is enabled, the queue
    removes items from itself as they are played.

    When not enabled, the queue acts like a regular playlist, and
    moves the position as tracks are played.

    In this mode, when a new track is queued, the position is set
    to play that track, and play will continue with that track
    until the queue is exhausted, and then the assigned playlist
    will be continued.

    TODO: Queue needs to be threadsafe!
    """

    def __init__(self, player, name, location=None):
        playlist.Playlist.__init__(self, name=name)

        self.__queue_has_tracks_val = False
        self.__current_playlist = self  # this should never be None
        self.player = player

        # hack for making docs work
        if player is not None:
            player.queue = self

        if location is not None:
            self.load_from_location(location)

        event.add_callback(self._on_option_set, '%s_option_set' % name)

        self.__opt_remove_item_when_played = '%s/remove_item_when_played' % name
        self.__opt_disable_new_track_when_playing = (
            '%s/disable_new_track_when_playing' % name
        )
        self.__opt_enqueue_begins_playback = '%s/enqueue_begins_playback' % name

        self._on_option_set(None, settings, self.__opt_remove_item_when_played)
        self._on_option_set(None, settings, self.__opt_disable_new_track_when_playing)

    def _on_option_set(self, evtype, settings, option):
        if option == self.__opt_remove_item_when_played:
            self.__remove_item_on_playback = settings.get_option(option, True)
            if len(self):
                self.__queue_has_tracks = True
        elif option == self.__opt_disable_new_track_when_playing:
            self.__disable_new_track_when_playing = settings.get_option(option, False)

    def set_current_playlist(self, playlist):
        """
        Sets the playlist to be processed in the queue

        :param playlist: the playlist to process
        :type playlist: :class:`xl.playlist.Playlist`

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `queue_current_playlist_changed`: indicates that the queue playlist has been changed
        """
        if playlist is self.__current_playlist:
            return
        elif playlist is None:
            playlist = self

        if playlist is self:
            self.__queue_has_tracks = True

        self.__current_playlist = playlist
        event.log_event('queue_current_playlist_changed', self, playlist)

    #: The playlist currently processed in the queue
    current_playlist = property(
        lambda self: self.__current_playlist, set_current_playlist
    )

    def get_next(self):
        """
        Retrieves the next track that will be played. Does not
        actually set the position. When you call next(), it should
        return the same track.

        This exists to support retrieving a track before it actually
        needs to be played, such as for pre-buffering.

        :returns: the next track to be played
        :rtype: :class:`xl.trax.Track` or None
        """
        if self.__queue_has_tracks and len(self):
            if self.__remove_item_on_playback:
                return self[0]
            else:
                return playlist.Playlist.get_next(self)
        elif self.current_playlist is not self:
            return self.current_playlist.get_next()
        else:
            return None

    def next(self, autoplay=True, track=None):
        """
        Goes to the next track, either in the queue, or in the current
        playlist.  If a track is passed in, that track is played

        :param autoplay: play the track in addition to returning it
        :type autoplay: bool
        :param track: if passed, play this track
        :type track: :class:`xl.trax.Track`

        .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

            * `playback_playlist_end`: indicates that the end of the queue has been reached
        """
        if track is None:
            if self.__queue_has_tracks:
                if not self.__remove_item_on_playback:
                    track = super().next()
                else:
                    try:
                        track = self.pop(0)
                    except IndexError:
                        pass

                # reached the end of the internal queue, don't repeat
                if track is None:
                    self.__queue_has_tracks = False

            if track is None and self.current_playlist is not self:
                track = self.current_playlist.next()

        if autoplay:
            self.player.play(track)

        if not track:
            event.log_event("playback_playlist_end", self, self.current_playlist)
        return track

    def prev(self):
        """
        Goes to the previous track
        """
        track = None
        if self.player.current:
            if self.player.get_time() < 5:
                if self.__queue_has_tracks and not self.__remove_item_on_playback:
                    position = self.current_position - 1
                    if position < 0:
                        position = 0 if len(self) else -1
                    self.current_position = position
                    track = self.current
                elif self.current_playlist is not self:
                    track = self.current_playlist.prev()

            if track is None:
                track = self.player.current
        else:
            track = self.current

        self.player.play(track)
        return track

    def get_current(self):
        """
        Gets the current track

        :returns: the current track
        :type: :class:`xl.trax.Track`
        """
        if self.player.current and self.current_position > 0:
            current = self.player.current
        else:
            current = playlist.Playlist.get_current(self)
            if current is None and self.current_playlist is not self:
                current = self.current_playlist.get_current()
        return current

    def get_current_position(self):
        if self.__remove_item_on_playback:
            return 0
        else:
            return playlist.Playlist.get_current_position(self)

    def set_current_position(self, position):
        if not self.__remove_item_on_playback:
            return playlist.Playlist.set_current_position(self, position)

    def is_play_enabled(self):
        ''':returns: True when calling play() will have no effect'''
        return not (self.player.is_playing() and self.__disable_new_track_when_playing)

    def play(self, track=None):
        """
        Starts queue processing with the given
        track preceding the queue content

        :param track: the track to play
        :type track: :class:`xl.trax.Track`
        """
        if self.player.is_playing():
            if not track or self.__disable_new_track_when_playing:
                return
        if not track:
            track = self.current
        if track:
            self.player.play(track)
            if self.__remove_item_on_playback:
                try:
                    del self[self.index(track)]
                except ValueError:
                    pass
        else:
            self.next()

    def queue_length(self):
        """
        Returns the number of tracks left to play in the queue's
        internal playlist.
        """
        if self.__remove_item_on_playback:
            return len(self)
        else:
            if not self.__queue_has_tracks:
                return -1
            else:
                return len(self) - (self.current_position + 1)

    def __set_queue_has_tracks(self, value):
        if value != self.__queue_has_tracks_val:
            oldpos = self.current_position
            self.__queue_has_tracks_val = value
            event.log_event(
                "playlist_current_position_changed",
                self,
                (self.current_position, oldpos),
            )

    # Internal value indicating whether the internal queue has tracks left to play
    __queue_has_tracks = property(
        lambda self: self.__queue_has_tracks_val, __set_queue_has_tracks
    )

    def __setitem__(self, i, value):
        """
        Overrides the playlist.Playlist list API.

        Allows us to ensure that when a track is added to an empty queue,
        we play it. Or not, depending on what the user wants.
        """
        old_len = playlist.Playlist.__len__(self)
        playlist.Playlist.__setitem__(self, i, value)

        # if nothing is queued, queue this track up
        if self.current_position == -1:
            if isinstance(i, slice):
                self.current_position = i.indices(len(self))[0] - 1
            else:
                self.current_position = i - 1

        self.__queue_has_tracks = True

        if (
            old_len == 0
            and settings.get_option('queue/enqueue_begins_playback', True)
            and old_len < playlist.Playlist.__len__(self)
        ):
            self.play()

    def _save_player_state(self, location):
        state = {}
        state['state'] = self.player.get_state()
        state['position'] = self.player.get_time()

        with open(location, 'wb') as f:
            pickle.dump(state, f, protocol=2)

    @common.threaded
    def _restore_player_state(self, location):
        if not settings.get_option("%s/resume_playback" % self.player._name, True):
            return

        try:
            with open(location, 'rb') as f:
                state = pickle.load(f)
        except Exception:
            return

        for req in ['state', 'position']:
            if req not in state:
                return

        self._do_restore_player_state(state)

    @common.idle_add()
    def _do_restore_player_state(self, state):

        if state['state'] in ['playing', 'paused']:

            start_at = None
            if state['position'] is not None:
                start_at = state['position']

            paused = state['state'] == 'paused' or settings.get_option(
                "%s/resume_paused" % self.player._name, False
            )

            self.player.play(self.get_current(), start_at=start_at, paused=paused)
