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

# It is encouraged that external modules should import from here,
# rather than directly from submodules.

"""
Provides the base for creating and managing Track objects.
"""

from xl.trax.track import Track
from xl.trax.trackdb import TrackDB
from xl.trax.search import (
    SearchResultTrack,
    search_tracks,
    search_tracks_from_string,
    TracksMatcher,
    TracksInList,
    TracksNotInList,
    match_track_from_string,
)
from xl.trax.util import (
    is_valid_track,
    get_album_tracks,
    get_uris_from_tracks,
    get_tracks_from_uri,
    sort_tracks,
    sort_result_tracks,
    get_rating_from_tracks,
)
