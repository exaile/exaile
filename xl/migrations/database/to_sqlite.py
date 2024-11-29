# Copyright (C) 2024  Johannes Sasongko <johannes sasongko org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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

import dbm
import glob
import os
import os.path
import pickle
import shelve

try:
    import berkeleydb
except ImportError:
    import bsddb3 as berkeleydb

from xl import common, sqlitedbm


def migrate(old_path: str, new_path: str):
    """
    Migrate to SQLite-based shelf database.

    The source can be a BsdDbShelf but can also be any of the built-in shelves,
    because there was a time (probably only during 4.0 beta?) when Exaile could
    produce non-bsddb shelves.
    It even supports old databases created on Python 2.

    :return: Whether a migration is performed
    """

    class Utf8Unpickler(pickle.Unpickler):
        def __init__(self, *args, **kwargs):
            kwargs['encoding'] = 'utf-8'
            super().__init__(*args, **kwargs)

    # Change shelve's unpickler to use UTF-8, for compatibility with shelves
    # created by Python 2.
    # This is safe to remove if we don't want the compatibility anymore.
    shelve.Unpickler = Utf8Unpickler

    # Read data from old db
    try:
        old_db = berkeleydb.hashopen(old_path, 'r')
    except (berkeleydb.db.DBNoSuchFileError, berkeleydb.db.DBInvalidArgError):
        try:
            old_db = dbm.open(old_path, 'r')
        except dbm.error:
            return False
    old_shelf = shelve.Shelf(old_db, protocol=common.PICKLE_PROTOCOL)
    del old_db  # Don't accidentally use the raw database
    items = list(old_shelf.items())
    old_shelf.close()

    # Set aside the old files as temporary backup
    bak_path = old_path + '.before-sqlite'
    old_group = _get_file_group(old_path)
    bak_group = [bak_path + old[len(old_path) :] for old in old_group]
    for old, bak in zip(old_group, bak_group):
        os.rename(old, bak)

    # Write data to new db
    new_shelf = shelve.Shelf(
        sqlitedbm.SqliteDbm(new_path, autocommit=False), protocol=common.PICKLE_PROTOCOL
    )
    for key, value in items:
        new_shelf[key] = value
    new_shelf.close()

    # # Remove the backup files
    # for bak in _get_file_group(bak_path):
    #     try:
    #         os.remove(bak)
    #     except Exception:
    #         pass

    return True


def _get_file_group(path: str) -> list[str]:
    """
    Get `path` (if exists) and `path.*` files.

    Databases like to create multiple files; this tries to get all of them.
    """
    group = glob.glob(path + '.*')
    if os.path.exists(path):
        group.insert(0, path)
    return group
