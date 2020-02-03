# Copyright (C) 2009-2010 Erin Drummond
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


class TreeItem:
    def __init__(self, id, name, has_been_expanded=False):
        self._id = id
        self._name = name
        self._type = type
        self._has_been_expanded = has_been_expanded

    def __repr__(self):
        return self._name

    # Getter and Setter crap
    def get_id(self):
        return self._id

    def get_name(self):
        return self._name

    def get_has_been_expanded(self):
        return self._has_been_expanded

    def set_has_been_expanded(self, value):
        self._has_been_expanded = value

    # this is the location in the TreeStore so that child objects can be added to this object (row_pointer should be a TreeIter object)
    def get_row_pointer(self):
        return self._row_pointer

    def set_row_pointer(self, value):
        self._row_pointer = value

    id = property(get_id)
    name = property(get_name)
    expanded = property(get_has_been_expanded, set_has_been_expanded)
    row_pointer = property(get_row_pointer, set_row_pointer)


class Artist(TreeItem):
    def __init__(self, id, name, has_been_expanded=False):
        TreeItem.__init__(self, id, name, has_been_expanded)
        self._albums = []

    # add an album to this artist
    def add_album(self, album):
        if isinstance(album, Album):
            album.artist_name = self.name
            self._albums.append(album)

    def get_albums(self):
        return self._albums

    albums = property(get_albums)


class Album(TreeItem):
    def __init__(self, id, name, has_been_expanded=False):
        TreeItem.__init__(self, id, name, has_been_expanded)
        self._tracks = []
        self._artist_name = "Default"

    def add_track(self, track):
        if isinstance(track, Track):
            track.artist_name = self.artist_name
            track.album_name = self.name
            self._tracks.append(track)

    def get_tracks(self):
        return self._tracks

    def get_artist_name(self):
        return self._artist_name

    def set_artist_name(self, value):
        self._artist_name = value

    tracks = property(get_tracks)
    artist_name = property(get_artist_name, set_artist_name)


class Track(TreeItem):
    def __init__(self, id, name, url):
        TreeItem.__init__(self, id, name)
        self._url = url
        self._artist_name = "http://jamendo.com"
        self._album = "http://jamendo.com"

    def get_url(self):
        return self._url

    def get_album_name(self):
        return self._album

    def set_album_name(self, value):
        self._album = value

    def get_artist_name(self):
        return self._artist_name

    def set_artist_name(self, value):
        self._artist_name = value

    url = property(get_url)
    # used for adding the track to the playlist initially
    artist_name = property(get_artist_name, set_artist_name)
    album_name = property(get_album_name, set_album_name)
