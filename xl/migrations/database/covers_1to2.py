# Copyright (C) 2009 Aren Olson (for the old_get_track_key function)
# Copyright (C) 2018 Johannes Sasongko <sasongko@gmail.com>
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

__all__ = ['migrate']

import logging
import os

import xl.collection
import xl.covers

logger = logging.getLogger(__name__)


def old_get_track_key(track):
    """
    Get the db mapping key for a track
    """
    album = track.get_tag_raw("album", join=True)
    compilation = track.get_tag_raw("__compilation")

    if compilation:
        value = track.get_tag_raw('albumartist')
        if value:
            tag = 'albumartist'
        else:
            tag = 'compilation'
            value = compilation
    elif album:
        tag = 'album'
        value = album
    else:
        # no album info, cant store it
        return None
    return (tag, tuple(value))


def migrate():
    """Migrate covers.db version 1 to 2 (Exaile 4.0)."""

    man = xl.covers.MANAGER
    if man.db.get('version', 1) != 1:
        return
    logger.info("Upgrading covers.db to version 2")

    valid_cachefiles = set()

    old_db = man.db
    new_db = {'version': 2}
    for coll in xl.collection.COLLECTIONS:
        for tr in coll.tracks.values():
            key = old_get_track_key(tr._track)
            value = old_db.get(key)
            if value:
                new_key = man._get_track_key(tr)
                new_db[new_key] = value
                if value.startswith('cache:'):
                    valid_cachefiles.add(value[6:])
    man.db = new_db
    man.save()

    cachedir = os.path.join(man.location, 'cache')
    for cachefile in frozenset(os.listdir(cachedir)) - valid_cachefiles:
        os.remove(os.path.join(cachedir, cachefile))
