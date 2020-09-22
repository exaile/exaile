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

"""
    General functions and classes shared in the codebase
"""

from collections import deque
import collections.abc
from functools import wraps, partial
import inspect
import logging
import os
import os.path
import pickle
import shelve
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import weakref

import bsddb3 as bsddb
from gi.repository import Gio, GLib, GObject

from xl import shelve_compat


logger = logging.getLogger(__name__)


# TODO: get rid of this. only plugins/cd/ uses it.
VALID_TAGS = (
    # Ogg Vorbis spec tags
    "title version album tracknumber artist genre performer copyright "
    "license organization description location contact isrc date "
    # Other tags we like
    "arranger author composer conductor lyricist discnumber labelid part "
    "website language encodedby bpm albumartist originaldate originalalbum "
    "originalartist recordingdate"
).split()

PICKLE_PROTOCOL = 2

# Default tags for track sorting. Unless you have good reason to do
# otherwise, use this.
# TODO: make this a setting?
BASE_SORT_TAGS = ('albumartist', 'date', 'album', 'discnumber', 'tracknumber', 'title')


def clamp(value, minimum, maximum):
    """
    Clamps a value to the given boundaries

    :param value: the value to clamp
    :param minimum: the minimum value to return
    :param maximum: the maximum value to return
    """
    return max(minimum, min(value, maximum))


def enum(**enums):
    """
    Creates an enum type

    :see: https://stackoverflow.com/a/1695250
    """
    return type('Enum', (), enums)


def sanitize_url(url):
    """
    Removes the password part from an url

    :param url: the URL to sanitize
    :type url: string
    :returns: the sanitized url
    """
    try:
        components = list(urllib.parse.urlparse(url))
        auth, host = components[1].split('@')
        username, password = auth.split(':')
    except (AttributeError, ValueError):
        pass
    else:
        # Replace password with fixed amount of "*"
        auth = ':'.join((username, 5 * '*'))
        components[1] = '@'.join((auth, host))
        url = urllib.parse.urlunparse(components)

    return url


def get_url_contents(url, user_agent):
    """
    Retrieves data from a URL and sticks a user-agent on it. You can use
    exaile.get_user_agent_string(pluginname) to get this.

    Added in Exaile 3.4

    :returns: Contents of page located at URL
    :raises: urllib.error.URLError
    """

    headers = {'User-Agent': user_agent}
    req = urllib.request.Request(url, None, headers)
    fp = urllib.request.urlopen(req)
    data = fp.read()
    fp.close()

    return data


def threaded(func):
    """
    A decorator that will make any function run in a new thread

    :param func: the function to run threaded
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()

    return wrapper


def synchronized(func):
    """
    A decorator to make a function synchronized - which means only one
    thread is allowed to access it at a time.

    This only works on class functions, and creates a variable in
    the instance called _sync_lock.

    If this function is used on multiple functions in an object, they
    will be locked with respect to each other. The lock is re-entrant.
    """

    @wraps(func)
    def wrapper(self, *__args, **__kw):
        try:
            rlock = self._sync_lock
        except AttributeError:
            from threading import RLock

            rlock = self.__dict__.setdefault('_sync_lock', RLock())
        rlock.acquire()
        try:
            return func(self, *__args, **__kw)
        finally:
            rlock.release()

    return wrapper


def _idle_callback(func, callback, *args, **kwargs):
    value = func(*args, **kwargs)
    if callback and callable(callback):
        callback(value)


def idle_add(callback=None):
    """
    A decorator that will wrap the function in a GLib.idle_add call

    NOTE: Although this decorator will probably work in more cases than
    the gtkrun decorator does, you CANNOT expect to get a return value
    from the function that calls a function with this decorator.  Instead,
    you must use the callback parameter.  If the wrapped function returns
    a value, it will be passed in as a parameter to the callback function.

    @param callback: optional callback that will be called when the
        wrapped function is done running
    """

    def wrap(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            GLib.idle_add(_idle_callback, f, callback, *args, **kwargs)

        return wrapped

    return wrap


def _glib_wait_inner(timeout, glib_timeout_func):
    # Have to hold the value in a mutable structure because python's scoping
    # rules prevent us assigning to an outer scope directly.
    #
    # Additionally, we hold source ids per-instance, otherwise this would
    # restrict calls across all instances of an object with the glib_wait*
    # decorators, which would have surprising results
    id_by_obj = weakref.WeakKeyDictionary()

    def waiter(function):
        # ensure this is only used on instance methods
        callargs = inspect.getfullargspec(function)
        if len(callargs.args) == 0 or callargs.args[0] != 'self':
            raise RuntimeError("Must only use glib_wait* on instance methods!")

        def thunk(*args, **kwargs):
            id_by_obj[args[0]] = None
            # if a function returns True, it wants to be called again; in that
            # case, treat it as an additional call, otherwise you can potentially
            # get lots of callbacks piling up
            if function(*args, **kwargs):
                delayer(*args, **kwargs)

        def delayer(*args, **kwargs):
            self = args[0]
            srcid = id_by_obj.get(self)
            if srcid:
                GLib.source_remove(srcid)
            id_by_obj[self] = glib_timeout_func(timeout, thunk, *args, **kwargs)

        return delayer

    return waiter


def glib_wait(timeout):
    """
    Decorator to make a function run only after 'timeout'
    milliseconds have elapsed since the most recent call to the
    function.

    For example, if a function was given a timeout of 1000 and
    called once, then again half a second later, it would run
    only once, 1.5 seconds after the first call to it.

    If arguments are given to the function, only the last call's set
    of arguments will be used.

    If the function returns a value that evaluates to True, it
    will be called again under the same timeout rules.

    .. warning:: Can only be used with instance methods
    """
    return _glib_wait_inner(timeout, GLib.timeout_add)


def glib_wait_seconds(timeout):
    """
    Same as glib_wait, but uses GLib.timeout_add_seconds instead
    of GLib.timeout_add and takes its timeout in seconds. See the
    glib documention for why you might want to use one over the
    other.
    """
    return _glib_wait_inner(timeout, GLib.timeout_add_seconds)


def profileit(func):
    """
    Decorator to profile a function
    """
    import cProfile
    import pstats

    @wraps(func)
    def wrapper(*args, **kwargs):
        prof = cProfile.Profile()
        res = prof.runcall(func, *args, **kwargs)
        stats = pstats.Stats(prof)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        print(">>>---- Begin profiling print")
        stats.print_stats()
        print(">>>---- End profiling print")
        prof = stats = None
        return res

    return wrapper


class classproperty:
    """
    Decorator allowing for class property access
    """

    def __init__(self, function):
        self.function = function

    def __get__(self, obj, type):
        return self.function(type)


class VersionError(Exception):
    """
    Represents version discrepancies
    """

    #: the error message
    message = None

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def __str__(self):
        return repr(self.message)


def open_file(path):
    """
    Opens a file or folder using the system configured program
    """
    platform = sys.platform
    if platform == 'win32':
        # pylint will error here on non-windows platforms unless we do this
        # pylint: disable-msg=E1101
        os.startfile(path)
        # pylint: enable-msg=E1101
    elif platform == 'darwin':
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def open_file_directory(path_or_uri):
    """
    Opens the parent directory of a file, selecting the file if possible.
    """
    f = Gio.File.new_for_commandline_arg(path_or_uri)
    platform = sys.platform
    if platform == 'win32':
        # We could run `explorer /select,filename`, but that doesn't support
        # reusing an existing Explorer window when selecting a file in a
        # directory that is already open.

        import ctypes

        CoInitialize = ctypes.windll.ole32.CoInitialize
        CoInitialize.argtypes = [ctypes.c_void_p]
        CoInitialize.restype = ctypes.HRESULT
        CoUninitialize = ctypes.windll.ole32.CoUninitialize
        CoUninitialize.argtypes = []
        CoUninitialize.restype = None
        ILCreateFromPath = ctypes.windll.shell32.ILCreateFromPathW
        ILCreateFromPath.argtypes = [ctypes.c_wchar_p]
        ILCreateFromPath.restype = ctypes.c_void_p
        ILFree = ctypes.windll.shell32.ILFree
        ILFree.argtypes = [ctypes.c_void_p]
        ILFree.restype = None
        SHOpenFolderAndSelectItems = ctypes.windll.shell32.SHOpenFolderAndSelectItems
        SHOpenFolderAndSelectItems.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        SHOpenFolderAndSelectItems.restype = ctypes.HRESULT

        CoInitialize(None)
        pidl = ILCreateFromPath(f.get_path())
        SHOpenFolderAndSelectItems(pidl, 0, None, 0)
        ILFree(pidl)
        CoUninitialize()
    elif platform == 'darwin':
        subprocess.Popen(["open", f.get_parent().get_parse_name()])
    else:
        subprocess.Popen(["xdg-open", f.get_parent().get_parse_name()])


def open_shelf(path):
    """
    Opens a python shelf file, used to store various types of metadata
    """
    shelve_compat.ensure_shelve_compat()

    # As of Exaile 4, new DBs will only be created as Berkeley DB Hash databases
    # using either bsddb3 (external) or bsddb (stdlib but sometimes removed).
    # Existing DBs created with other backends will be migrated to Berkeley DB.
    # We do this because BDB is generally considered more performant,
    # and because gdbm currently doesn't work at all in MSYS2.

    # Some DBM modules don't use the path we give them, but rather they have
    # multiple filenames. If the specified path doesn't exist, double check
    # to see if whichdb returns a result before trying to open it with bsddb
    force_migrate = False
    if not os.path.exists(path):
        from dbm import whichdb

        if whichdb(path) is not None:
            force_migrate = True

    if not force_migrate:
        try:
            db = bsddb.hashopen(path, 'c')
            return shelve.BsdDbShelf(db, protocol=PICKLE_PROTOCOL)
        except bsddb.db.DBInvalidArgError:
            logger.warning("%s was created with an old backend, migrating it", path)
        except Exception:
            raise

    # special case: zero-length file
    if not force_migrate and os.path.getsize(path) == 0:
        os.unlink(path)
    else:
        from xl.migrations.database.to_bsddb import migrate

        migrate(path)

    db = bsddb.hashopen(path, 'c')
    return shelve.BsdDbShelf(db, protocol=PICKLE_PROTOCOL)


class LimitedCache(collections.abc.MutableMapping):
    """
    Simple cache that acts much like a dict, but has a maximum # of items
    """

    def __init__(self, limit):
        self.limit = limit
        self.order = deque()
        self.cache = dict()

    def __iter__(self):
        return self.cache.__iter__()

    def __len__(self):
        return self.cache.__len__()

    def __contains__(self, item):
        return self.cache.__contains__(item)

    def __delitem__(self, item):
        del self.cache[item]
        self.order.remove(item)

    def __getitem__(self, item):
        val = self.cache[item]
        self.order.remove(item)
        self.order.append(item)
        return val

    def __setitem__(self, item, value):
        self.cache[item] = value
        if item in self.order:
            self.order.remove(item)
        self.order.append(item)
        while len(self) > self.limit:
            del self.cache[self.order.popleft()]

    def __repr__(self):
        '''prevent repr(self) from changing cache order'''
        return repr(self.cache)

    def __str__(self):
        '''prevent str(self) from changing cache order'''
        return str(self.cache)

    def keys(self):
        return self.cache.keys()


class cached:
    """
    Decorator to make a function's results cached
    does not cache if there is an exception.

    .. note:: This probably breaks on functions that modify their arguments
    """

    def __init__(self, limit):
        self.limit = limit

    @staticmethod
    def _freeze(d):
        return frozenset(d.items())

    def __call__(self, f):
        try:
            f._cache
        except AttributeError:
            f._cache = LimitedCache(self.limit)

        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f._cache[(args, self._freeze(kwargs))]
            except KeyError:
                pass
            ret = f(*args, **kwargs)
            try:
                f._cache[(args, self._freeze(kwargs))] = ret
            except TypeError:  # args can't be hashed
                pass
            return ret

        return wrapper

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return partial(self.__call__, obj)


def walk(root):
    """
    Walk through a Gio directory, yielding each file

    Files are enumerated in the following order: first the
    directory, then the files in that directory. Once one
    directory's files have all been listed, it moves on to
    the next directory. Order of files within a directory
    and order of directory traversal is not specified.

    :param root: a :class:`Gio.File` representing the
        directory to walk through
    :returns: a generator object
    :rtype: :class:`Gio.File`
    """
    queue = deque()
    queue.append(root)

    while len(queue) > 0:
        dir = queue.pop()
        yield dir
        try:
            for fileinfo in dir.enumerate_children(
                "standard::type,"
                "standard::is-symlink,standard::name,"
                "standard::symlink-target,time::modified",
                Gio.FileQueryInfoFlags.NONE,
                None,
            ):
                fil = dir.get_child(fileinfo.get_name())
                # FIXME: recursive symlinks could cause an infinite loop
                if fileinfo.get_is_symlink():
                    target = fileinfo.get_symlink_target()
                    if "://" not in target and not os.path.isabs(target):
                        fil2 = dir.get_child(target)
                    else:
                        fil2 = Gio.File.new_for_uri(target)
                    # already in the collection, we'll get it anyway
                    if fil2.has_prefix(root):
                        continue
                type = fileinfo.get_file_type()
                if type == Gio.FileType.DIRECTORY:
                    queue.append(fil)
                elif type == Gio.FileType.REGULAR:
                    yield fil
        except GLib.Error:  # why doesnt gio offer more-specific errors?
            logger.exception("Unhandled exception while walking on %s.", dir)


def walk_directories(root):
    """
    Walk through a Gio directory, yielding each subdirectory

    :param root: a :class:`Gio.File` representing the
        directory to walk through
    :returns: a generator object
    :rtype: :class:`Gio.File`
    """
    yield root
    directory = None
    subdirectory = None

    try:
        for fileinfo in root.enumerate_children(
            'standard::name,standard::type', Gio.FileQueryInfoFlags.NONE, None
        ):
            if fileinfo.get_file_type() == Gio.FileType.DIRECTORY:
                directory = root.get_child(fileinfo.get_name())

                for subdirectory in walk_directories(directory):
                    yield subdirectory
    except GLib.Error:
        logger.exception(
            "Unhandled exception while walking dirs on %s, %s, %s",
            root,
            directory,
            subdirectory,
        )


class TimeSpan:
    """
    Calculates the number of days, hours, minutes,
    and seconds in a time span
    """

    #: number of days
    days = 0
    #: number of hours
    hours = 0
    #: number of minutes
    minutes = 0
    #: number of seconds
    seconds = 0

    def __init__(self, span):
        """
        :param span: Time span in seconds
        :type span: float
        """
        try:
            span = float(span)
        except (ValueError, TypeError):
            span = 0

        span, self.seconds = divmod(span, 60)
        span, self.minutes = divmod(span, 60)
        self.days, self.hours = divmod(span, 24)

    def __repr__(self):
        span = self.days * 24 + self.hours
        span = span * 60 + self.minutes
        span = span * 60 + self.seconds
        return '%s(%s)' % (self.__class__.__name__, span)

    def __str__(self):
        return '%dd, %dh, %dm, %ds' % (
            self.days,
            self.hours,
            self.minutes,
            self.seconds,
        )


class MetadataList:
    """
    Like a list, but also associates an object of metadata
    with each entry.

    ``(get|set|del)_meta_key`` are the metadata interface - they
    allow the metadata to act much like a dictionary, with a few
    optimizations.

    List aspects that are not supported:
        * sort
        * comparisons other than equality
        * multiply
    """

    __slots__ = ['__list', 'metadata']

    def __init__(self, iterable=[], metadata=[]):
        self.__list = list(iterable)
        meta = list(metadata)
        if meta and len(meta) != len(self.__list):
            raise ValueError("Length of metadata must match length of items.")
        if not meta:
            meta = [None] * len(self.__list)
        self.metadata = meta

    def __repr__(self):
        return "MetadataList(%s)" % self.__list

    def __len__(self):
        return len(self.__list)

    def __iter__(self):
        return self.__list.__iter__()

    def __add__(self, other):
        l = MetadataList(self, self.metadata)
        l.extend(other)
        return l

    def __iadd__(self, other):
        self.extend(other)
        return self

    def __eq__(self, other):
        if isinstance(other, MetadataList):
            other = list(other)
        return self.__list == other

    def __getitem__(self, i):
        val = self.__list.__getitem__(i)
        if isinstance(i, slice):
            return MetadataList(val, self.metadata.__getitem__(i))
        else:
            return val

    def __setitem__(self, i, value):
        self.__list.__setitem__(i, value)
        if isinstance(value, MetadataList):
            metadata = list(value.metadata)
        else:
            metadata = [None] * len(value)
        self.metadata.__setitem__(i, metadata)

    def __delitem__(self, i):
        self.__list.__delitem__(i)
        self.metadata.__delitem__(i)

    def append(self, other, metadata=None):
        self.insert(len(self), other, metadata=metadata)

    def extend(self, other):
        self[len(self) : len(self)] = other

    def insert(self, i, item, metadata=None):
        if i >= len(self):
            i = len(self)
            e = len(self) + 1
        else:
            e = i
        self[i:e] = [item]
        self.metadata[i:e] = [metadata]

    def pop(self, i=-1):
        item = self[i]
        del self[i]
        return item

    def remove(self, item):
        del self[self.index(item)]

    def reverse(self):
        self.__list.reverse()
        self.metadata.reverse()

    def index(self, i, start=0, end=None):
        if end is None:
            return self.__list.index(i, start)
        else:
            return self.__list.index(i, start, end)

    def count(self, i):
        return self.__list.count(i)

    def get_meta_key(self, index, key, default=None):
        if not self.metadata[index]:
            return default
        return self.metadata[index].get(key, default)

    def set_meta_key(self, index, key, value):
        if not self.metadata[index]:
            self.metadata[index] = {}
        self.metadata[index][key] = value

    def del_meta_key(self, index, key):
        if not self.metadata[index]:
            raise KeyError(key)
        del self.metadata[index][key]
        if not self.metadata[index]:
            self.metadata[index] = None


class ProgressThread(GObject.GObject, threading.Thread):
    """
    A basic thread with progress updates. The thread should emit
    the progress-update signal periodically. The contents must
    be number between 0 and 100, or a tuple of (n, total) where
    n is the current step.
    """

    __gsignals__ = {
        'progress-update': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (GObject.TYPE_PYOBJECT,),
        ),
        # TODO: Check if 'stopped' is required
        'done': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        GObject.GObject.__init__(self)
        threading.Thread.__init__(self)
        self.setDaemon(True)

    def stop(self):
        """
        Stops the thread
        """
        self.emit('done')

    def run(self):
        """
        Override and make sure that the 'progress-update'
        signal is emitted regularly with the progress
        """
        pass


class SimpleProgressThread(ProgressThread):
    """
    Simpler version of ProgressThread that uses a generator to
    manage the thread and its progress. Instead of overriding
    run, just pass a callable that returns a generator to
    the constructor.

    The callable must either yield a number between 0 and 100,
    or yield a tuple of (n, total) where n is the current step.

    ::

        def long_running_thing():
            l = len(stuff)
            try:
                for i in stuff:
                    yield (i, l)
            finally:
                # if the thread is stopped, GeneratorExit will
                # be raised the next time yield is called
                pass
    """

    def __init__(self, target, *args, **kwargs):
        ProgressThread.__init__(self)
        self.__target = (target, args, kwargs)
        self.__stop = False

    def stop(self):
        """
        Causes the thread to stop at the next yield point
        """
        self.__stop = True

    def run(self):
        """
        Runs a generator
        """
        target, args, kwargs = self.__target

        try:
            for progress in target(*args, **kwargs):
                self.emit('progress-update', progress)
                if self.__stop:
                    break
        except GeneratorExit:
            pass
        except Exception:
            logger.exception("Unhandled exception")
        finally:
            self.emit('done')


class PosetItem:
    def __init__(self, name, after, priority, value=None):
        """
        :param name: unique identifier for this item
        :type name: string
        :param after: which items this item comes after
        :type after: list of string
        :param priority: tiebreaker, higher values come later
        :type priority: int
        :param value: arbitrary data associated with the item
        """
        self.name = name
        self.after = list(after)
        self.priority = priority
        self.children = []
        self.value = value


def order_poset(items):
    """
    :param items: poset to order
    :type items: list of :class:`PosetItem`
    """
    items = {item.name: item for item in items}
    for name, item in items.items():
        for after in item.after:
            k = items.get(after)
            if k:
                k.children.append(item)
            else:
                item.after.remove(after)
    result = []
    next = [i[1] for i in items.items() if not i[1].after]
    while next:
        current = sorted((i.priority, i.name, i) for i in next)
        result.extend(i[2] for i in current)
        nextset = dict()
        for i in current:
            for c in i[2].children:
                nextset[c.name] = c
        removals = []
        for name, item in nextset.items():
            for after in item.after:
                if after in nextset:
                    removals.append(name)
                    break
        for r in removals:
            del nextset[r]
        next = list(nextset.values())
    return result


class LazyDict:
    __slots__ = ['_dict', '_funcs', 'args', '_locks']

    def __init__(self, *args):
        self.args = args
        self._dict = {}
        self._funcs = {}
        self._locks = {}

    def __setitem__(self, item, value):
        if inspect.isfunction(value):
            self._funcs[item] = value
        else:
            self._dict[item] = value

    def __getitem__(self, item):
        lock = self._locks.get(item, threading.Lock())
        with lock:
            try:
                return self._dict[item]
            except KeyError:
                self._locks[item] = lock
                val = self._funcs[item](item, *self.args)
                self._dict[item] = val
                return val

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default


class _GioFileStream:

    __slots__ = ['stream']

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.stream.close()

    def seek(self, offset, whence=os.SEEK_CUR):
        if whence == os.SEEK_CUR:
            self.stream.seek(offset, GLib.SeekType.CUR)
        elif whence == os.SEEK_SET:
            self.stream.seek(offset, GLib.SeekType.SET)
        elif whence == os.SEEK_END:
            self.stream.seek(offset, GLib.SeekType.END)
        else:
            raise IOError("Invalid whence")

    def tell(self):
        return self.stream.tell()


class GioFileInputStream(_GioFileStream):
    """
    Wrap a Gio.File so it looks like a python file object for reading.

    TODO: More complete wrapper
    """

    __slots__ = ['stream', 'gfile']

    def __init__(self, gfile):
        self.gfile = gfile
        self.stream = Gio.DataInputStream.new(gfile.read())

    def __iter__(self):
        return self

    def __next__(self):
        r = self.stream.read_line()[0]
        if not r:
            raise StopIteration()
        return r.decode('utf-8')

    def read(self, size=None):
        if size:
            return self.stream.read_bytes(size).get_data().decode('utf-8')
        else:
            return self.gfile.load_contents()[1].decode('utf-8')

    def readline(self):
        return self.stream.read_line()[0].decode('utf-8')


class GioFileOutputStream(_GioFileStream):
    """
    Wrapper around Gio.File for writing like a python file object
    """

    __slots__ = ['stream']

    def __init__(self, gfile, mode='w'):
        if mode != 'w':
            raise IOError("Not implemented")

        self.stream = gfile.replace('', False, Gio.FileCreateFlags.REPLACE_DESTINATION)

    def flush(self):
        self.stream.flush()

    def write(self, s):
        if isinstance(s, str):
            s = s.encode('utf-8', 'surrogateescape')
        return self.stream.write(s)


def subscribe_for_settings(section, options, self):
    """
    Allows you designate attributes on an object to be dynamically
    updated when a particular setting changes. If you want to be
    notified of a setting update, use a @property for the attribute.

    Only works for a options in a single section

    :param section: Settings section
    :param options: Dictionary of key: option name, value: attribute on
                    'self' to set when the setting has been updated. The
                    attribute must already have a default value in it
    :param self:    Object to set attribute values on

    :returns: A function that can be called to unsubscribe

    .. versionadded:: 3.5.0
    """

    from xl import event
    from xl import settings

    def _on_option_set(unused_name, unused_object, data):
        attrname = options.get(data)
        if attrname is not None:
            setattr(self, attrname, settings.get_option(data, getattr(self, attrname)))

    for k in options:
        if not k.startswith('%s/' % section):
            raise ValueError("Option is not part of section %s" % section)
        _on_option_set(None, None, k)

    return event.add_callback(
        _on_option_set, '%s_option_set' % section.replace('/', '_')
    )


class AsyncLoader:
    """
    Async loader based on a generator
    Threaded, load it and put it in `result_list`
    """

    def __init__(self, item_generator):
        """
        Constructs and already start processing (starts thread)
        :param item_generator: iterable
        """
        self.__end = False
        self.__result_list = []
        self.__thread = threading.Thread(target=self.run, args=(item_generator,))
        self.__thread.start()

    def run(self, item_generator):
        """
        Process items putting in `result_list`
        :param item_generator: iterable
        :return: None
        """
        for i in item_generator:
            if self.__end:
                break
            self.__result_list.append(i)
            if self.__end:
                break

    def end(self, timeout=None):
        """
        Request process ending if it doesn't occurs in timeout
        :param timeout: float representing seconds or None to wait infinitely (default)
        :return: None
        """
        self.__thread.join(timeout)
        self.__end = True

    def ended(self):
        """
        If it has ended
        :return: bool
        """
        return not self.__thread.is_alive()

    @property
    def result(self):
        """
        Gets the result
        :return: list
        """
        return self.__result_list[:]


class LowestStr(str):
    """String subclass that always sorts as the lowest value"""

    def __lt__(self, _):
        return True


class HighestStr(str):
    """String subclass that always sorts as the highest value"""

    def __lt__(self, _):
        return False


# vim: et sts=4 sw=4
