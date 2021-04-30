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

from typing import Callable, Iterable, List, Optional, TypeVar

from gi.repository import Gio
from gi.repository import GLib

from xl import metadata
from xl.trax.track import Track
from xl.trax.search import search_tracks, TracksMatcher

T = TypeVar('T')


def is_valid_track(location):
    """
    Returns whether the file at the given location is a valid track

    :param location: the location to check
    :type location: string
    :returns: whether the file is a valid track
    :rtype: boolean
    """
    extension = Gio.File.new_for_commandline_arg(location).get_basename().split(".")[-1]
    return extension.lower() in metadata.formats


def get_uris_from_tracks(tracks):
    """
    Returns all URIs for tracks

    :param tracks: the tracks to retrieve the URIs from
    :type tracks: list of :class:`xl.trax.Track`
    :returns: the uris
    :rtype: list of string
    """
    return [track.get_loc_for_io() for track in tracks]


def get_tracks_from_uri(uri):
    """
    Returns all valid tracks located at uri

    :param uri: the uri to retrieve the tracks from
    :type uri: string
    :returns: the retrieved tracks
    :rtype: list of :class:`xl.trax.Track`
    """
    tracks = []

    gloc = Gio.File.new_for_uri(uri)

    # don't do advanced checking on streaming-type uris as it can fail or
    # otherwise be terribly slow.
    # TODO: move uri definition somewhere more common for easy reuse?
    if gloc.get_uri_scheme() in ('http', 'mms', 'cdda'):
        return [Track(uri)]

    try:
        file_type = gloc.query_info(
            "standard::type", Gio.FileQueryInfoFlags.NONE, None
        ).get_file_type()
    except GLib.Error:  # E.g. cdda
        file_type = None
    if file_type == Gio.FileType.DIRECTORY:
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


def sort_tracks(
    fields: Iterable[str],
    items: Iterable[T],
    trackfunc: Optional[Callable[[T], Track]] = None,
    reverse: bool = False,
    artist_compilations: bool = False,
) -> List[T]:
    """
    Sorts tracks.

    :param fields: tag names to sort by
    :param items: the tracks to sort,
        alternatively use *trackfunc*
    :param trackfunc: function to get a *Track*
        from an item in the *items* iterable
    :param reverse: whether to sort in reversed order
    """
    fields = list(fields)  # we need the index method
    if trackfunc is None:
        trackfunc = lambda tr: tr
    keyfunc = lambda tr: [
        trackfunc(tr).get_tag_sort(field, artist_compilations=artist_compilations)
        for field in fields
    ]
    return sorted(items, key=keyfunc, reverse=reverse)


def sort_result_tracks(fields, trackiter, reverse=False, artist_compilations=False):
    """
    Sorts SearchResultTracks, ie. the output from a search.

    Same params as sort_tracks.
    """
    return sort_tracks(
        fields, trackiter, lambda tr: tr.track, reverse, artist_compilations
    )


def get_rating_from_tracks(tracks):
    """
    Returns the common rating for all tracks or
    simply 0 if not all tracks have the same
    rating. Same goes if the amount of tracks
    is 0 or more than the internal limit.

    :param tracks: the tracks to retrieve the rating from
    :type tracks: iterable
    """
    if len(tracks) < 1:
        return 0

    # TODO: still needed?
    #    if len(tracks) > settings.get_option('rating/tracks_limit', 100):
    #        return 0

    rating = tracks[0].get_rating()

    for track in tracks:
        if track.get_rating() != rating:
            return 0

    return rating


def get_album_tracks(tracksiter, track, artist_compilations=False):
    """
    Get any tracks from the given iterable that appear to be part of
    the same album as track. If track is in the iterable, it will be
    included in the result. If there is insufficient information to
    determine the album, the empty list will be returned, even if the
    track is in the iterable.
    """
    if not all(track.get_tag_raw(t) for t in ['artist', 'album']):
        return []
    matchers = [
        TracksMatcher(track.get_tag_search(t, artist_compilations=artist_compilations))
        for t in ('artist', 'album')
    ]
    return (r.track for r in search_tracks(tracksiter, matchers))


def recursive_tracks_from_file(gfile: Gio.File) -> Iterable[Track]:
    """
    Get recursive tracks from Gio.File
    If it's a directory, expands
    Gets only valid tracks
    """
    ftype = gfile.query_info(
        'standard::type', Gio.FileQueryInfoFlags.NONE, None
    ).get_file_type()
    if ftype == Gio.FileType.DIRECTORY:
        file_infos = gfile.enumerate_children(
            'standard::name', Gio.FileQueryInfoFlags.NONE, None
        )
        files = (gfile.get_child(fi.get_name()) for fi in file_infos)
        for sub_gfile in files:
            for i in recursive_tracks_from_file(sub_gfile):
                yield i
    else:
        uri = gfile.get_uri()
        if is_valid_track(uri):
            yield Track(uri)
