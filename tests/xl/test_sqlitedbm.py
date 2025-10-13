# Copyright (C) 2025  Johannes Sasongko <johannes sasongko org>
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


import os.path
import sqlite3
import tempfile

import pytest

from xl import sqlitedbm


def test_needs_rw_to_write():
    with tempfile.TemporaryDirectory(prefix="exaile-") as tmpdir:
        dbpath = os.path.join(tmpdir, "music.db")

        db = sqlitedbm.SqliteDbm(dbpath, mode='rwc')
        db[b'key1'] = b'value1'
        del db
        db = sqlitedbm.SqliteDbm(dbpath, mode='rw')
        db[b'key2'] = b'value2'
        del db
        db = sqlitedbm.SqliteDbm(dbpath, mode='ro')
        with pytest.raises(sqlite3.OperationalError):
            db[b'key3'] = b'value3'


def test_needs_rwc_to_create():
    with tempfile.TemporaryDirectory(prefix="exaile-") as tmpdir:
        dbpath = os.path.join(tmpdir, "music.db")

        with pytest.raises(sqlite3.OperationalError):
            sqlitedbm.SqliteDbm(dbpath, mode='ro')
        with pytest.raises(sqlite3.OperationalError):
            sqlitedbm.SqliteDbm(dbpath, mode='rw')


def test_no_autocommit():
    with tempfile.TemporaryDirectory(prefix="exaile-") as tmpdir:
        dbpath = os.path.join(tmpdir, "music.db")

        db = sqlitedbm.SqliteDbm(dbpath, autocommit=False)
        db[b'key1'] = b'value1'
        del db
        # Should still flush on close.
        db = sqlitedbm.SqliteDbm(dbpath, mode='ro')
        assert db[b'key1'] == b'value1'


def test_operations():
    with tempfile.TemporaryDirectory(prefix="exaile-") as tmpdir:
        dbpath = os.path.join(tmpdir, "music.db")

        db = sqlitedbm.SqliteDbm(dbpath)
        assert len(db) == 0
        db[b'key1'] = b'value1'
        db[b'key2'] = b'value2'
        assert b'key1' in db
        assert db[b'key1'] == b'value1'
        del db[b'key1']
        assert len(db) == 1
        assert list(db.items()) == [(b'key2', b'value2')]
        db.close()
        with pytest.raises(Exception):
            len(db)


def test_persistence():
    with tempfile.TemporaryDirectory(prefix="exaile-") as tmpdir:
        dbpath = os.path.join(tmpdir, "music.db")

        db = sqlitedbm.SqliteDbm(dbpath)
        db[b'key1'] = b'value1'
        del db
        db = sqlitedbm.SqliteDbm(dbpath, mode='ro')
        assert list(db.items()) == [(b'key1', b'value1')]


def test_context_manager():
    with tempfile.TemporaryDirectory(prefix="exaile-") as tmpdir:
        dbpath = os.path.join(tmpdir, "music.db")

        with sqlitedbm.SqliteDbm(dbpath, mode='rwc') as db:
            pass
        with pytest.raises(Exception):
            len(db)
