# Copyright (C) 2006 Adam Olsen
#
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from xl import common
import logging

logger = logging.getLogger(__name__)

import threading
import re
import os
import traceback
import tempfile
import shutil
try:
    from sqlite3 import dbapi2 as sqlite
    SQLITE_AVAIL = True
except ImportError:
    try:
        from pysqlite2 import dbapi2 as sqlite
        SQLITE_AVAIL = True
    except ImportError:
        SQLITE_AVAIL = False

# sqlite.enable_shared_cache(True)

from gi.repository import GLib


class DBOperationalError(Exception):

    def __init__(self, message):
        """ Create a new DBOperationalError

            :Parameters:
                - `message`: The message that will be displayed to the user
        """
        self.message = message

    def __repr__(self):
        msg = "%s: %s"
        return msg % (self.__class__.__name__, self.message,)

    def __str__(self):
        return self.__repr__()


def the_cutter(field):
    """
        Cuts "THE " off of the beginning of any field for better sorting
    """
    field = field.lower()
    if field.find("the ") == 0:
        return field.replace("the ", "", 1)
    else:
        return field


def lstrip_special(field):
    """
        Strip special chars off the beginning of a field for sorting. If
        stripping the chars leaves nothing the original field is returned with
        only whitespace removed.
    """
    lowered = field.lower()
    stripped = lowered.lstrip(" `~!@#$%^&*()_+-={}|[]\\\";'<>?,./")
    if stripped:
        return stripped
    return lowered.lstrip()


class DBManager(object):
    """
        Manages the database connection
    """

    def __init__(self, db_loc, start_timer=True):
        """
            Initializes and connects to the database
        """

        self.db_loc = db_loc
        self.db = self.__get_db()

        self.pool = dict()
        self.timer_id = None
        self.p = '?'
        self.functions = []

        cur = self.db.cursor()
        cur.execute("PRAGMA synchronize=OFF")
        cur.execute("PRAGMA count_changes=0")
        cur.execute("PRAGMA auto_vacuum=1")
        cur.execute("PRAGMA cache_size=4000")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.execute("PRAGMA fullsync=0")
        cur.execute("PRAGMA case_sensitive_like=0")
        cur.close()
        self._cursor = self.db.cursor()

        self.add_function_create(('THE_CUTTER', 1, the_cutter))
        self.add_function_create(('LSTRIP_SPEC', 1, lstrip_special))

    def _close_thread(self):
        """
            Closes the db in the pool for the current thread
        """
        name = threading.currentThread().getName()
        if name == "MainThread":
            return
        if name in self.pool:
            self.pool[name].close()
            del self.pool[name]
            logger.debug("Closed db for thread %s" % name)

    def _get_from_pool(self):
        """
            Returns a database connection specific to the current thread
        """
        name = threading.currentThread().getName()
        if name == "MainThread" or self.db_loc == ":memory:":
            return self.db
        if name not in self.pool:
            db = self.__get_db()
            for tup in self.functions:
                db.create_function(tup[0], tup[1], tup[2])
            self.pool[name] = db
            logger.debug("Created db for thread %s" % name)
            logger.debug(self.pool)

        db = self.pool[name]
        return db

    def add_function_create(self, tup):
        """
            Adds a function that will be created in all pooled dbs
        """
        self.db.create_function(tup[0], tup[1], tup[2])
        self.functions.append(tup)

    def cursor(self, new=False):
        """
            Returns the write cursor
        """
        if new:
            return self._get_from_pool().cursor()
        else:
            return self._cursor

    def __get_db(self):
        """
            Returns a connection
        """
        try:
            db = sqlite.connect(self.db_loc, check_same_thread=False)
            db.text_factory = lambda x: unicode(x, 'utf-8', 'ignore')
        except sqlite.OperationalError as e:
            raise DBOperationalError(str(e))

        return db

    def close(self):
        """
            Closes the connection
        """
        if self.timer_id:
            GLib.source_remove(self.timer_id)

    def execute(self, query, args=None):
        """
            Executes a query
        """
        cur = self._cursor
        if not args:
            args = []
        try:
            cur.execute(query, args)
        except:
            common.log_exception(log=logger)

    def select(self, query, args=[]):
        """
            Runs a select and returns all rows.  This is only for small
            select operations.  If you want to do a large select, use
            DBManager.realcursor()
        """
        db = self._get_from_pool()
        cur = db.cursor()
        cur.execute(query, args)
        rows = []

        while True:
            try:
                row = cur.fetchone()
                if not row:
                    break
                rows.append(row)
            except:
                common.log_exception(log=logger)

        cur.close()

        return rows

    def realcursor(self):
        """
            Returns a new cursor from the database
        """
        return self.db.cursor()

    def record_count(self, table, where, args):
        """
            Returns the number of rows matched for the query in the database
        """
        db = self._get_from_pool()
        cur = db.cursor()
        cur.execute("SELECT count(*) AS c FROM %s WHERE %s" % (table, where), args)
        row = cur.fetchone()
        cur.close()
        return row[0]

    def commit(self):
        """
            Commits the database
        """
        if threading.currentThread().getName() == 'MainThread':
            self.db.commit()
        else:
            GLib.idle_add(self.db.commit)

    def read_one(self, table, items, where, args):
        """
            Returns the first row matched for the query in the database
        """
        cur = self.db.cursor()
        query = "SELECT %s FROM %s WHERE %s LIMIT 1" % \
            (items, table, where)

        cur.execute(query, args)
        row = cur.fetchone()

        cur.close()
        return row


def insert_id(cur):
    cur.execute('SELECT LAST_INSERT_ROWID()')
    row = cur.fetchone()
    return row[0]
