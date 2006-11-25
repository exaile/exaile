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

import sys, threading, re, os, fileinput, traceback
try:
    from sqlite3 import dbapi2 as sqlite
    SQLITE_AVAIL = True
except ImportError:
    try:
        from pysqlite2 import dbapi2 as sqlite
        SQLITE_AVAIL = True
    except ImportError:
        SQLITE_AVAIL = False

try:
    import MySQLdb
    MYSQL_AVAIL = True
    ProgrammingError = MySQLdb.ProgrammingError
except ImportError:
    MYSQL_AVAIL = False

try:
    import pyPgSQL.PgSQL
    PGSQL_AVAIL = True
    PostgresOperationalError = pyPgSQL.PgSQL.OperationalError
except:
    PGSQL_AVAIL = False
#sqlite.enable_shared_cache(True)

from traceback import print_exc
import gobject

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
        if start_timer:
            self.timer_id = gobject.timeout_add(2 * 60 * 60, self.commit)

        cur = self.db.cursor()
        cur.execute("PRAGMA synchronize=OFF")
        cur.execute("PRAGMA count_changes=0")
        cur.execute("PRAGMA auto_vacuum=1")
        cur.execute("PRAGMA cache_size=4000")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.execute("PRAGMA fullsync=0")
        cur.execute("PRAGMA cast_sensitive_like=0")
        cur.close()
        self._cursor = self.db.cursor()

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
            db = sqlite.connect(self.db_loc, check_same_thread=True)
        except sqlite.OperationalError, e:
            raise DBOperationalError(str(e))

        return db

    def close(self):
        """
            Closes the connection
        """
        if self.timer_id:
            gobject.source_remove(self.timer_id)

    def check_version(self, path, echo=True):
        """
            Checks the database version and updates it if necessary
        """
        version = 0
        row = self.read_one("db_version", "version", "1=1", tuple())
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
        lines = []
        for line in open(file):
            if not line.startswith("--"):
                lines.append(line)

        data = "".join(lines)
        data = data.replace("\n", " ")
        lines = data.split(";")

        for line in lines:
            if line.strip():
                self.execute(line)
        self.db.commit()

    def execute(self, query, args=None):
        """
            Executes a query on the main event loop
        """
        if threading.currentThread().getName() == 'MainThread':
            self._execute(query, args)
        else:
            gobject.idle_add(self._execute, query, args)
        
    def _execute(self, query, args=None):
        """
            Executes a query
        """
        cur = self._cursor
        if not args: args = []
        try:
            cur.execute(query, args)
        except:
            traceback.print_exc()
            print query, args

    def select(self, query, args=[]):
        """
            Runs a select and returns all rows.  This is only for small
            select operations.  If you want to do a large select, use
            DBManager.realcursor()
        """
        db = self._get_from_pool()
        cur = db.cursor()
        cur.execute(query, args)
        all = cur.fetchall()
        cur.close()

        return all

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
            gobject.idle_add(self.db.commit)

    def _get_from_pool(self):
        """
            Returns a database connection specific to the current thread
        """
        name = threading.currentThread().getName()
        if name == "MainThread": return self.db
        if not self.pool.has_key(name):
            db = self.__get_db()
            for tup in self.functions:
                db.create_function(tup[0], tup[1], tup[2])
            self.pool[name] = db
            print "Created db for thread %s" % name
            print self.pool

        db = self.pool[name]
        return db

    def _close_thread(self):
        """
            Closes the db in the pool for the current thread
        """
        name = threading.currentThread().getName()
        if name == "MainThread": return
        if self.pool.has_key(name):
            self.pool[name].close()
            del self.pool[name]
            print "Closed db for thread %s" % name

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

    def update(self, table, vals, where, args, new=False):
        """
            Updates a table or creates a new row
        """
        if threading.currentThread().getName() == 'MainThread':
            self._update(table, vals, where, args, new)
        else:
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
                if not isinstance(val, str) or not isinstance(val, unicode):
                    val = unicode(val)

                val = val.decode("utf-8", 'replace')
                values.append(val)

            left = ", ".join(keys)
            right = ", ".join(['?' for x in keys])
            query = "REPLACE INTO %s( %s ) VALUES( %s )" % (table, left, right)
            try:
                cur.execute(query, tuple(values))
            except Exception, e:
                print "Error on: %s" % query
                print e
            return
        else:
            values = []
            keys = []
            for k, v in vals.iteritems():

                if not isinstance(v, str): v = str(v)
                v = v.decode("utf-8", 'replace')
                keys.append("%s=?" % k)
                values.append(v)

            values.extend(args)

            query = "UPDATE %s SET %s WHERE %s" % (table, ", ".join(keys), where)
            cur.execute(query, values)
