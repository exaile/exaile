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
try:
    import cPickle as pickle
except:
    import pickle

from xl import playlist, settings, event, common

logger = logging.getLogger(__name__)

class PlayQueue(playlist.Playlist):

    """
        Manages the queue of songs to be played
    """

    def __init__(self, player, location=None):
        self.current_playlist = None
        self.current_pl_track = None
        playlist.Playlist.__init__(self, name="Queue")
        self.player = player
        player._set_queue(self)
        if location is not None:
            self.load_from_location(location)

    def set_current_playlist(self, playlist):
        self.current_playlist = playlist

    def set_current_pl_track(self, track):
        self.current_pl_track = track

    def next(self, player=True, track=None):
        """
            Goes to the next track, either in the queue, or in the current
            playlist.  If a track is passed in, that track is played

            :param player: play the track in addition to returning it
            :param track: if passed, play this track
        """
        if not track:
            try:
                track = self.pop(0)
                self.current_pos = 0
                self.current_playing = True
                if self.current_playlist:
                    self.current_playlist.current_playing = False
            except IndexError:
                if self.current_playlist:
                    track = self.current_playlist.next()
                    self.current_playlist.current_playing = True
                    self.current_playing = False
                else:
                    track = None
        if player:
            self.player.play(track)
        if not track:
            event.log_event("playback_playlist_end", self,
                        self.current_playlist)
        return track

    def prev(self):
        track = None
        if self.player.current:
            if self.player.get_time() < 5 and self.current_playlist:
                track = self.current_playlist.prev()
            else:
                track = self.player.current
        else:
            track = self.current
        self.player.play(track)
        return track

    def get_current(self):
        if self.player.current and self.current_pos > 0:
            current = self.player.current
        else:
            current = playlist.Playlist.get_current(self)
            if current == None and self.current_playlist:
                current = self.current_playlist.get_current()
        return current

    def get_current_position(self):
        return 0

    def set_current_position(self, position):
        return

    def play(self, track=None):
        """
            start playback, either from the passed track or from already
            queued tracks
        """
        if self.player.is_playing() and not track:
            return
        if not track:
            track = self.current
        if track:
            self.player.play(track)
            try:
                del self[self.index(track)]
            except ValueError:
                pass
        else:
            self.next()

    def _save_player_state(self, location):
        state = {}
        state['state'] = self.player.get_state()
        state['position'] = self.player.get_time()
        state['_playtime_stamp'] = self.player._playtime_stamp
        f = open(location, 'wb')
        pickle.dump(state, f, protocol = 2)
        f.close()

    @common.threaded
    def _restore_player_state(self, location):
        if not settings.get_option("player/resume_playback", True):
            return

        try:
            f = open(location, 'rb')
            state = pickle.load(f)
            f.close()
        except:
            return

        for req in ['state', 'position', '_playtime_stamp']:
            if req not in state:
                return

        if state['state'] in ['playing', 'paused']:
            event.log_event("playback_player_resume", self.player, None)
            vol = self.player._get_volume()
            self.player._set_volume(0)
            self.play(self.get_current())

            if self.player.current:
                self.player.seek(state['position'])
                if state['state'] == 'paused' or \
                        settings.get_option("player/resume_paused", False):
                    self.player.toggle_pause()
                self.player._playtime_stamp = state['_playtime_stamp']

            self.player._set_volume(vol)
