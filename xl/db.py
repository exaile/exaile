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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import sys, threading, xlmisc, re, os, fileinput
from pysqlite2 import dbapi2 as sqlite
from traceback import print_exc
import gobject

class DBManager(object):
    """
        Manages the database connection
    """
    def __init__(self, db_loc):
        """
            Initializes and connects to the database
        """
        self.db = sqlite.connect(db_loc)
        self.db_loc = db_loc
        self.pool = dict()
        self.timer = xlmisc.MiscTimer(self.commit, 2 * 60 * 60)

        if db_loc != ":memory:":
            cur = self.db.cursor()
            cur.execute("PRAGMA synchronize=OFF")
            cur.execute("PRAGMA count_changes=0")
            cur.execute("PRAGMA auto_vacuum=1")
            cur.execute("PRAGMA cache_size=4000")
            cur.execute("PRAGMA temp_store=MEMORY")
            cur.execute("PRAGMA fullsync=0")
            cur.close()
        
        self._cursor = self.db.cursor()
        self.timer.start()

    def check_version(self, path, echo=True):
        """
            Checks the database version and updates it if necessary
        """
        version = 0
        row = self.read_one("version", "version", "1", tuple())
        if row:
            version = int(row[0])

        files = os.listdir(path)
        versions = []
        for file in files:
            m = re.search("changes(\d+)\.sql", file)
            if not m: continue
            ver = int(m.group(1))
            file = "changes%.4d.sql" % ver
            if ver > version:
                if echo:
                    xlmisc.log("Importing sql changes file %s" % file)
                self.import_sql("%s/%s" % (path, file))

    def import_sql(self, file):
        """
            Imports an SQL file
        """
        for line in fileinput.input(file):
            self._exec(line)
        self.db.commit()
                     
    def cursor(self):
        """
            Returns a db cursor
        """
        return self._cursor


    def execute(self, query, args=[], now=False):
        """
            Executes a query
        """
        if now: self._exec(query, args)
        else: gobject.idle_add(self._exec, query, args)

    def _exec(self, query, args=None):
        """
            Executes a query
        """
        if not args: args = []
        try:
            cur = self._cursor
            cur.execute(query, args)
        except:
            print query
	    print_exc()

    def select(self, query, args=[]):
        """
            Runs a select and returns all rows.  This is only for small
            select operations.  If you want to do a large select, use
            DBManager.realcursor()
        """
        cur = self._cursor
        cur.execute(query, args)
        return cur.fetchall()

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
            Queues a commit in the main event thread
        """
        gobject.idle_add(self._commit)

    def _commit(self):
        """
            Commits the database
        """
        self.db.commit()

    def _get_from_pool(self):
        """
            Returns a database connection specific to the current thread
        """
        name = threading.currentThread().getName()
        if name == "MainThread": return self.db
        if not self.pool.has_key(name):
            db = sqlite.connect(self.db_loc)
            self.pool[name] = db

        db = self.pool[name]
        return db

    def read_one(self, table, items, where, args):
        """
            Returns the first row matched for the query in the database
        """
        name = threading.currentThread().getName()
        if name == "MainThread": cur = self._cursor
        else: cur = self._get_from_pool().cursor()
        query = "SELECT %s FROM %s WHERE %s LIMIT 1" % \
           (items, table, where)

        cur.execute(query, args)   
        row = cur.fetchone()

        if name != "MainThread": cur.close()
        return row

    def update(self, table, vals, where, args, new=False):
        """
            Updates the database based on the query... or, if the specified row
            does not currently exist in the database, a new row is created
        """
        gobject.idle_add(self._update, table, vals, where, args, new)

    def _update(self, table, vals, where, args, new=False): 
        """
            Updates the database based on the query... or, if the specified row
            does not currently exist in the database, a new row is created
        """
        cur = self._cursor

        if new:
            keys = vals.keys()
            values = []
            for key in keys:
                val = vals[key]
                if not isinstance(val, str):
                    val = str(val)

                val = val.decode("utf-8", 'replace')
                val = val.replace("\"", "\"\"")
                values.append('"%s"' % val)

            left = ", ".join(keys)
            right = ", ".join(values)

            query = "REPLACE INTO %s( %s ) VALUES( %s )" % (table, left, right)
            try:
                cur.execute(query)
            except OperationalError:
                print "Error on: %s" % query
            return
        else:
            values = []
            for k, v in vals.iteritems():

                if not isinstance(v, str): v = str(v)
                v = v.decode("utf-8", 'replace')
                values.append("%s=\"%s\" " % (k, v.replace('"', r'""')))

            query = "UPDATE %s SET %s WHERE %s" % (table, ", ".join(values), where)
            cur.execute(query, args)
