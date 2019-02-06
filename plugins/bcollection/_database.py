# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import os.path
import sqlite3

from time import sleep

from gi.repository import Gtk

from xl.common import enum
from xl.nls import gettext as _

from _base import PLUGIN_INFO, SETTINGS, Logger, create_event
from _utils import FileFilter, normalize


#: Logger: Logger to file
_LOGGER = Logger(__name__)

#: enum: Statuses to database connection
ConnectionStatus = enum(Fine=0, Initial=1, Error=2)


class CantCreateConnectionException(Exception):
    """
        Exception to express when can't create connection to database
    """
    #: Event: Triggered when can't create connection to database
    EVENT = create_event('cant-create-connection')

    def __init__(self, ex, _path):
        """
            Constructor
            :param ex: parent exception
            :param path: str
        """
        Exception.__init__(self, ex)
        self.EVENT.log()


class CantSelectException(Exception):
    """
        Exception to express when can't execute select on database
    """
    def __init__(self, ex, sql, values):
        """
            Constructor
            :param ex: parent exception
            :param sql: str
            :param values: list
        """
        Exception.__init__(self, ex)
        _LOGGER.exception(
            'could not select from database: ex=%s (sql=%s, values=%s)',
            ex, sql, values
        )


class FileChooserDialog(Gtk.FileChooserDialog):
    """
        A wrapper to Gtk.FileChooserDialog
    """
    def __init__(self, parent, notify=lambda: None):
        """
            Constructor
            :param parent: Gtk.Window
        """
        Gtk.FileChooserDialog.__init__(
            self, _("Select a beets media library database"),
            parent, Gtk.FileChooserAction.OPEN,
            ('gtk-cancel', Gtk.ResponseType.CANCEL,
             'gtk-open', Gtk.ResponseType.OK)
        )

        self.add_filter(
            FileFilter(
                _('Beets / SQLite database'),
                # blb sl2 sl3 db db2 db3 sdb s2db s3db sqlite
                # sqlite2 sqlite3
                ['*.[b|B][l|L][b|B]', '*.[s|S][l|L][2|3]',
                 '*.[d|D][b|B]', '*.[d|D][b|B][2|3]',
                 '*.[s|S][d|D][b|B]', '*.[s|S][2|3][d|D][b|B]',
                 '*.[s|S][q|Q][l|L][i|I][t|T][e|E]',
                    '*.[s|S][q|Q][l|L][i|I][t|T][e|E][2|3]']
            )
        )
        self.add_filter(FileFilter(_('All files'), ['*']))

        #: callable: To notify after change
        self.__notify = notify

    def __call__(self, *_args, **_kwargs):
        """
            Run it
            :param _args:
            :param _kwargs:
            :return: None
        """
        self.run()

    def run(self):
        """
            Gtk.Dialog.run
            It tries to already set at correct file
            Set the new value to config and notify change if user chooses a file
            :return: int - response ID
        """
        database = SETTINGS['database']
        if database:
            self.set_filename(database)

        result = super(self.__class__, self).run()
        if result == Gtk.ResponseType.OK:
            SETTINGS['database'] = self.get_filename()
            try:
                self.__notify()
            except Exception:
                _LOGGER.exception(
                    'error notifying database file change'
                )

        self.hide()
        return result


def _get_letter_group(o):
    """
        Group it based on first letter
        :param o: object
        :return: "#" | "A" ... "Z" | "0-9"
    """
    if isinstance(o, int):
        # For years, to only consider the first 3 digits
        return ('%04d' % o)[:-1]
    else:
        try:
            letter_group = normalize(o)[0]
        except IndexError:  # only for '' values
            letter_group = "#"
        else:
            if letter_group.isdigit() or not letter_group.isalpha():
                letter_group = '#'

    return letter_group.upper()


def _create_connection():
    """
        Get a new database connection
        :return: sqlite3.Connection or None
    """
    database_path = SETTINGS['database']
    if os.path.isfile(database_path):
        try:
            connection = sqlite3.connect(database_path, cached_statements=1)
        except sqlite3.OperationalError as ex:
            # When a database is accessed by multiple connections,
            # and one of the processes modifies the database,
            # the SQLite database is locked until that transaction is committed.
            # The timeout parameter specifies how long the connection should
            # wait for the lock to go away until raising an exception.
            # The default for the timeout parameter is 5.0 (five seconds).
            raise CantCreateConnectionException(ex, database_path)
        else:
            # Configure functions
            connection.create_function('normalize', 1, normalize)
            connection.create_function('get_letter_group', 1, _get_letter_group)

            return connection
    else:
        raise CantCreateConnectionException(
            Exception('file does not exists'), database_path
        )


def execute_select(sql, values):
    """
        Executes a select sql
        :param sql: str
        :param values: list
        :yield: sqlite3.Row
    """
    try:
        connection = _create_connection()
    except CantCreateConnectionException:
        _LOGGER.exception('cannot connect to database')
        raise

    try:
        cursor = connection.cursor()
    except sqlite3.Error:
        _LOGGER.exception('could not create database cursor')
    else:
        _LOGGER.debug(
            'executes sql: "%s", params=%s', sql, values
        )
        try:
            cursor.execute(sql, values)
        except sqlite3.Error as ex:
            raise CantSelectException(ex, sql, values)
        else:
            item = cursor.fetchone()
            while item is not None:
                yield item
                item = cursor.fetchone()
    finally:
        connection.close()


def get_connection_status():
    """
        Gets the current connection status
        :return: ConnectionStatus
    """
    if SETTINGS['database']:
        try:
            connection = _create_connection()
        except:
            return ConnectionStatus.Error
        else:
            connection.close()
            return ConnectionStatus.Fine
    else:
        return ConnectionStatus.Initial


def execute_delete(path):
    """
        Execute a delete for a path

        Returns connection to let commit or rollback
        :param path: unicode
        :return: sqlite3.Connection
    """
    try:
        connection = _create_connection()
    except CantCreateConnectionException:
        _LOGGER.exception('cannot connect to database')
        raise

    cursor = connection.cursor()

    # Retries on lock
    for _ in range(30):
        try:
            cursor.execute("DELETE FROM `items` WHERE `path` = ?;", [path])
        except sqlite3.OperationalError as e:
            if str(e) != "database is locked":
                raise
            else:
                sleep(1)
        else:
            break

    if cursor.rowcount > 0:
        return connection
    else:
        connection.close()
        return None
