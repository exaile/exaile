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


__all__ = ['SqliteDbm']


from collections.abc import Iterator, MutableMapping
import operator
import os
from os import PathLike
import shelve
import sqlite3
import sys
from typing import Any, Literal
import urllib.parse


class SqliteDbm(MutableMapping[bytes, bytes]):
    """
    DBM-compatible database implemented on top of SQLite.

    This class can operate on files created by dbm.sqlite (Python >= 3.13) and
    vice versa. The main difference is in how sqlite3.connect is called: this
    class uses check_same_thread=False and allows autocommit to be configured.
    """

    autocommit: bool
    conn: sqlite3.Connection

    def __init__(
        self,
        path: str | bytes | PathLike[str] | PathLike[bytes],
        *,
        autocommit: bool = True,
        mode: Literal['ro', 'rw', 'rwc'] = 'rwc',
    ):
        self.autocommit = autocommit
        path_urlquoted = urllib.parse.quote(os.fsencode(path))
        uri = f"file:{path_urlquoted}?mode={mode}"
        if sys.version_info >= (3, 13):
            self.conn = conn = sqlite3.connect(
                uri, autocommit=autocommit, check_same_thread=False, uri=True
            )
        else:
            self.conn = conn = sqlite3.connect(
                uri,
                check_same_thread=False,
                isolation_level="IMMEDIATE" if autocommit else "DEFERRED",
                uri=True,
            )
        # Our database is a Dict table with (key, value) columns.
        # Python DBM interface uses bytes as the key and value type, which
        # corresponds to SQLite BLOB.
        # This doesn't use WITHOUT ROWID <https://www.sqlite.org/withoutrowid.html>
        # because our rows tend to be longer than the 200 B threshold mentioned.
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS Dict (key BLOB PRIMARY KEY NOT NULL, value BLOB NOT NULL)"
            )
        except Exception:
            conn.close()
            del self.conn
            raise

    def close(self) -> None:
        if hasattr(self, "conn"):
            try:
                self.sync()
            finally:
                self.conn.close()
                del self.conn

    def sync(self) -> None:
        if not self.autocommit:
            self.conn.commit()

    def __contains__(self, key: str | bytes) -> bool:
        key = self.__fix_type(key)
        return (
            self.conn.execute("SELECT NULL FROM Dict WHERE key = ?", (key,)).fetchone()
            is not None
        )

    __del__ = close

    def __delitem__(self, key: str | bytes) -> None:
        key = self.__fix_type(key)
        if self.conn.execute("DELETE FROM Dict WHERE key = ?", (key,)).rowcount == 0:
            raise KeyError(key)

    # TODO: Can use ->Self in Python>=3.11
    def __enter__(self) -> 'SqliteDbm':
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def __getitem__(self, key: str | bytes) -> bytes:
        key = self.__fix_type(key)
        result = self.conn.execute(
            "SELECT value FROM Dict where key = ?", (key,)
        ).fetchone()
        if result is None:
            raise KeyError(key)
        return result[0]

    def __iter__(self) -> Iterator[bytes]:
        return map(operator.itemgetter(0), self.conn.execute("SELECT key FROM Dict"))

    def __len__(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM Dict").fetchone()[0]

    def __setitem__(self, key: str | bytes, value: str | bytes) -> None:
        key = self.__fix_type(key)
        value = self.__fix_type(value)
        self.conn.execute("REPLACE INTO Dict VALUES (?, ?)", (key, value))

    @staticmethod
    def __fix_type(obj: Any) -> bytes:
        if isinstance(obj, bytes):
            return obj
        if isinstance(obj, str):
            return obj.encode('utf-8')
        raise TypeError(
            "key/value must be bytes or str (will be encoded to UTF-8 bytes)"
        )
