#!/usr/bin/env python

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

try:
    import cPickle as pickle
except ImportError:
    import pickle

import gobject
from xl import media

SEARCH_ITEMS = ('artist', 'album', 'title')
SORT_ORDER = ('album', 'track', 'artist', 'title')

def get_sort_tuple(field, track):
    """
        Returns the sort tuple for a single track

        @type   field: str
        @param  field: the field to sort by
        @type   track: L{media.Track}
        @param  track: the track from which to retrieve the sort tuple

        @rtype: tuple
        @return: a tuple containing the sortable items for a track
    """

    items = [getattr(track, field)]
    for item in SORT_ORDER:
        items.append(getattr(track, item))

    items.append(track)
    return tuple(items)

def sort_tracks(field, tracks, reverse=False):
    """
        Sorts tracks by the field passed

        @type   field: str
        @param  field: the field to sort by
        @type   tracks: list
        @param  tracks: the tracks to sort
        @type   reverse: bool
        @param  reverse: True to reverse the sort order

        @rtype:  list
        @return: the sorted list of tracks
    """

    sort_order = [field].extend(SORT_ORDER)
    tracks = [get_sort_tuple(field, t) for t in tracks]
    tracks.sort()
    if reverse: tracks.reverse()

    return [t[-1:][0] for t in tracks]

class TrackDB(gobject.GObject):
    """
        Manages the track database. 

        Allows you to add, remove, retrieve, search, save and load
        L{media.Track} objects.

        This particular implementation is done using L{pickle}
    """

    # signals
    __gsignals__ = {
        'track_added': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
        'track_removed': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
    }

    def __init__(self, location=None):
        self.tracks = dict()
        self.location = location

        if location:
            self.load_from_location(location)

    def load_from_location(self, location):
        """
            Loads track data from a pickle location

            @type  location: str
            @param location: The location of the location
        """

        f = open(location, 'rb')
        self.tracks = pickle.load(f)
        f.close()

    def save_to_location(self, location=None):
        """
            Saves track data to a pickle location.

            @type  location: str
            @param location: The location of a location.  This is optional, and if
                         none is specified, it will use the location location
                         passed into the constructor
        """

        if not location:
            location = self.location

        if not location:
            raise AttributeError("You did not specify a location to save the db")

        f = file(location, 'w')
        pickle.dump(f, self.tracks)
        f.close()

    def add(self, track):
        """
            Adds a track to the database of tracks

            @type  track: L{media.Track} object
            @param track: The track you want to add to the database
        """
    
        self.tracks[track.loc] = track

        self.emit('track_added', track)

    def remove(self, track):
        """
            Removes a track from the database

            @type  track: L{media.Track} object
            @param track: The track you want to remove
        """

        if track.loc in self.tracks:
            del self.tracks[track]

            self.emit('track_removed', track)


    def search(self, keyword, sort_field=None):
        """
            Searches the track database for a list of tracks
        
            @type   keyword: str
            @param  keyword: The string you want to match
            
            @rtype:  list
            @return: A list of tracks matching the search terms
        """
        kw = keyword.lower()

        tracks = []
        for k, track in self.tracks.iteritems():
            for item in SEARCH_ITEMS:
                v = getattr(track, item).lower()
                if v.find(kw) > -1:
                    tracks.append(track)

        return tracks
