# Copyright (C) 2011 Adam Olsen
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

from xl import event


class PlaybackAdapter:
    """
    Basic class which listens for playback changes
    """

    def __init__(self, player):

        self.__player = player
        self.__events = (
            'playback_track_start',
            'playback_track_end',
            'playback_player_end',
            'playback_toggle_pause',
            'playback_error',
        )

        for e in self.__events:
            event.add_callback(getattr(self, 'on_%s' % e), e, player)

        if player.current is not None:
            self.on_playback_track_start('playback_track_start', player, player.current)

            if player.is_paused():
                self.on_playback_toggle_pause(
                    'playback_toggle_pause', player, player.current
                )

    def destroy(self):
        """
        Cleanups
        """
        for e in self.__events:
            event.remove_callback(getattr(self, 'on_%s' % e), e, self.__player)

    def on_playback_track_start(self, event, player, track):
        """Override"""
        pass

    def on_playback_track_end(self, event, player, track):
        """Override"""
        pass

    def on_playback_player_end(self, event, player, track):
        """Override"""
        pass

    def on_playback_toggle_pause(self, event, player, track):
        """Override"""
        pass

    def on_playback_error(self, event, player, message):
        """Override"""
        pass


class QueueAdapter:
    """
    Basic class which listens for queue changes
    """

    def __init__(self, queue):
        self.__queue = queue

        event.add_callback(
            self.on_queue_current_playlist_changed,
            'queue_current_playlist_changed',
            queue,
        )
        event.add_callback(
            self.__on_playlist_current_position_changed,
            'playlist_current_position_changed',
        )
        event.add_callback(self.__on_playlist_tracks_added, 'playlist_tracks_added')
        event.add_callback(self.__on_playlist_tracks_removed, 'playlist_tracks_removed')

    def destroy(self):
        """
        Cleanups
        """
        event.remove_callback(
            self.on_queue_current_playlist_changed,
            'queue_current_playlist_changed',
            self.__queue,
        )
        event.remove_callback(
            self.__on_playlist_current_position_changed,
            'playlist_current_position_changed',
        )
        event.remove_callback(self.__on_playlist_tracks_added, 'playlist_tracks_added')
        event.remove_callback(
            self.__on_playlist_tracks_removed, 'playlist_tracks_removed'
        )

    def __on_playlist_current_position_changed(self, event, playlist, positions):
        """
        Forwards the event if emitted by the queue
        """
        if playlist is self.__queue.current_playlist:
            self.on_queue_current_position_changed(event, playlist, positions)

    def __on_playlist_tracks_added(self, event, playlist, tracks):
        """
        Forwards the event if emitted by the queue
        """
        if playlist is self.__queue.current_playlist:
            self.on_queue_tracks_added(event, playlist, tracks)

    def __on_playlist_tracks_removed(self, event, playlist, tracks):
        """
        Forwards the event if emitted by the queue
        """
        if playlist is self.__queue.current_playlist:
            self.on_queue_tracks_removed(event, playlist, tracks)

    def on_queue_current_playlist_changed(self, event, queue, playlist):
        """Override"""
        pass

    def on_queue_current_position_changed(self, event, playlist, positions):
        """Override"""
        pass

    def on_queue_tracks_added(self, event, queue, tracks):
        """Override"""
        pass

    def on_queue_tracks_removed(self, event, queue, tracks):
        """Override"""
        pass
