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

import sys, threading, re, os, fileinput
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
    def __init__(self, type='sqlite', username='',
        host='localhost', password='', database='', start_timer=True):
        """
            Initializes and connects to the database
        """
        
        self.type = type
        self.db_loc = host
        self.username = username
        self.host = host
        self.password = password
        self.database = database
        self.db = self.__get_db()

        self.pool = dict()
        self.timer_id = None
        if start_timer:
            self.timer_id = gobject.timeout_add(2 * 60 * 60, self.commit)

        if type == 'sqlite': 
            cur = self.db.cursor()
            cur.execute("PRAGMA synchronize=OFF")
            cur.execute("PRAGMA count_changes=0")
            cur.execute("PRAGMA auto_vacuum=1")
            cur.execute("PRAGMA cache_size=4000")
            cur.execute("PRAGMA temp_store=MEMORY")
            cur.execute("PRAGMA fullsync=0")
            cur.close()
        
        self._cursor = self.db.cursor()

    def __get_db(self):
        """
            Returns a connection
        """
        if self.type == 'sqlite':
            self.p = "?"
            if not SQLITE_AVAIL:
                raise DBOperationalError("SQLite driver is not available")
            try:
               db = sqlite.connect(self.db_loc)
            except sqlite.OperationalError, e:
                raise DBOperationalError(str(e))
        elif self.type == 'pgsql':
            self.p = "%s"
            if not PGSQL_AVAIL:
                raise DBOperationalError("PostgreSQL driver is not available")

            db = pyPgSQL.PgSQL.connect(host=self.host, user=self.username,
                password=self.password, database=self.database)
        else:
            self.p = "%s"
            if not MYSQL_AVAIL: 
                raise DBOperationalError("MySQL driver is not available")
            try:
                db = MySQLdb.Connect(user=self.username, passwd=self.password,
                    host=self.host, db=self.database)
            except MySQLdb.OperationalError, e:
                raise DBOperationalError(str(e))

        return db

    def close(self):
        """
            Closes the connection
        """
        if self.type == 'mysql':
            self.db.close()

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
                line = self.sanitize(line + ";")
                self._exec(line)
        self.db.commit()

    def sanitize(self, line):
        """
            Converts a line to the current db spec
        """
        if self.type == 'pgsql' or self.type == 'sqlite':
            m = re.search("PRIMARY KEY\((.*)\)\s?\);", line)
            if m:
                args = m.group(1)
                args = re.sub("\(.*?\)", "", args)
                line = re.sub("PRIMARY KEY\((.*)\)\s?\);",
                    "PRIMARY KEY( %s ) );" % args, line)
        return line 
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
        name = threading.currentThread().getName()
        if name == "MainThread": cur = self._cursor
        else: cur = self._get_from_pool().cursor()

        cur.execute(query, args)
        all = cur.fetchall()
        if name != "MainThread": cur.close()

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
            db = self.__get_db()
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

    def update(self, table, vals, where, args, new=False, immediate=False):
        """
            Updates the database based on the query... or, if the specified row
            does not currently exist in the database, a new row is created
        """
        if not immediate:
            gobject.idle_add(self._update, table, vals, where, args, new)
        else:
            self._update(table, vals, where, args, new)
            self.db.commit()

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
            right = ", ".join([self.p for x in keys])
            query = "INSERT INTO %s( %s ) VALUES( %s )" % (table, left, right)
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
                keys.append("%s=%s" % (k, self.p))
                values.append(v)

            values.extend(args)

            query = "UPDATE %s SET %s WHERE %s" % (table, ", ".join(keys), where)
            cur.execute(query, values)
