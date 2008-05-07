# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xl import trackdb

def save_to_m3u(playlist, path):
    """
        Saves a Playlist to an m3u file
    """
    handle = open(path, "w")

    handle.write("#EXTM3U\n")
    if playlist.get_name() != '':
        handle.write("#PLAYLIST: %s\n" % playlist.get_name())

    for track in songs:
        handle.write("#EXTINF:%d,%s\n%s\n" % (track.duration,
            track.title, track.loc))

    handle.close()

def import_from_m3u(path):
    pass

def save_to_pls(playlist, path):
    pass

def import_from_pls(path):
    pass

class Playlist(trackdb.TrackDB):
    """
        Represents a playlist, which is basically just a TrackDB
        with ordering.
    """
    def __init__(self, location=None, pickle_attrs=[]):
        self.ordered_tracks = []
        self.current_pos = -1
        self.current_playing = False
        pickle_attrs += ['ordered_tracks', 'current_pos', 'current_playing']
        trackdb.TrackDB.__init__(self, location=location,
                pickle_attrs=pickle_attrs)

    def add(self, track, location=None):
        """
            insert the track into the playlist at the specified
            location (default: append)
        """
        self.add_tracks([track], location)

    def add_tracks(self, tracks, location=None):
        """
            like add(), but takes a list of tracks instead of a single one
        """
        if location == None:
            self.ordered_tracks.extend(tracks)
        else:
            self.ordered_tracks = self.ordered_tracks[:location] + \
                    tracks + self.ordered_tracks[location:]
        for t in tracks:
            trackdb.TrackDB.add(self, t)
        
        if location >= self.current_pos:
            self.current_pos += len(tracks)

    def remove(self, index):
        """
            removes the track at the specified index from the playlist
        """
        self.remove_tracks(index, index)

    def remove_tracks(self, start, end):
        end = end + 1
        removed = self.ordered_tracks[start:end]
        self.ordered_tracks = self.ordered_tracks[:start] + \
                self.ordered_tracks[end:]
        for t in removed:
            trackdb.TrackDB.remove(t)

        if end < self.current_pos:
            self.current_pos -= len(removed)
        elif start <= self.current_pos <= end:
            self.current_pos = start+1

    def get_tracks(self):
        return self.ordered_tracks[:]

    def get_current_pos(self):
        return self.current_pos

    def get_current(self):
        if self.current_pos >= len(self.ordered_tracks) or \
                self.current_pos == -1:
            return None
        else:
            return self.ordered_tracks[self.current_pos]

    def next(self):
        if len(self.ordered_tracks) == 0:
            return None
        self.current_pos += 1
        if self.current_pos >= len(self.ordered_tracks):
            self.current_pos = -1
        return self.get_current()

    def prev(self):
        self.current_pos -= 1
        if self.current_pos < 0:
            self.current_pos = 0
        return self.get_current()

