# Copyright (C) 2008-2009 Adam Olsen
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

import gio
from xl import metadata
from xl.trax.track import Track


def is_valid_track(loc):
    """
        Returns whether the file at loc is a valid track,
        right now determines based on file extension
    """
    extension = gio.File(loc).get_basename().split(".")[-1]
    return extension.lower() in metadata.formats

def get_tracks_from_uri(uri):
    """
        Returns all valid tracks located at uri
    """
    tracks = []

    gloc = gio.File(uri)
    # don't do advanced checking on streaming-type uris as it can fail or
    # otherwise be terribly slow.
    # TODO: move uri definition somewhere more common for easy reuse?

    if gloc.get_uri_scheme() in ('http', 'mms'):
        return [Track(uri)]

    file_type = gloc.query_info("standard::type").get_file_type()
    if file_type == gio.FILE_TYPE_DIRECTORY:
        # TODO: refactor Library so we dont need the collection obj
        from xl.collection import Library, Collection
        tracks = Collection('scanner')
        lib = Library(uri)
        lib.set_collection(tracks)
        lib.rescan()
        tracks = tracks.get_tracks()
    else:
        tracks = [Track(uri)]
    return tracks

def sort_tracks(fields, trackiter, reverse=False):
    """
        Sorts tracks.

        :param fields: An iterable of tag names
                       to sort by.
        :param trackiter: An iterable of Track objects to be sorted.
        :param reverse: Whether to sort in reverse.
    """
    fields = list(fields) # we need the index method
    artist_compilations = True
    keyfunc = lambda tr: [tr.get_tag_sort(field,
        artist_compilations=artist_compilations) for field in fields]
    return sorted(trackiter, key=keyfunc, reverse=reverse)


def sort_result_tracks(fields, trackiter, reverse=False):
    """
        Sorts SearchResultTracks, ie. the output from a search.

        Same params as sort_tracks.
    """
    artist_compilations = True
    keyfunc = lambda tr: [tr.track.get_tag_sort(field,
        artist_compilations=artist_compilations) for field in fields]
    return sorted(trackiter, key=keyfunc, reverse=reverse)

