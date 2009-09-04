# Copyright (C) 2008-2009 Adam Olsen 
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import locale, logging, random, string, sys, threading, time, traceback
from functools import wraps
from xl.nls import gettext as _

logger = logging.getLogger(__name__)
_TESTING = False  # set to True for testing

VALID_TAGS = (
    # Ogg Vorbis spec tags
    "title version album tracknumber artist genre performer copyright "
    "license organization description location contact isrc date "

    # Other tags we like
    "arranger author composer conductor lyricist discnumber labelid part "
    "website language encodedby bpm albumartist originaldate originalalbum "
    "originalartist recordingdate"
    ).split()

PICKLE_PROTOCOL=2


def get_default_encoding():
    return 'utf-8' # TODO: This is probably not right....

# log() exists only so as to not break compatibility, new code
# should not use it as it may br dropped in the future
def log(message):
    logger.info(message + "  (Warning, using deprecated logger)")

# use this for general logging of exceptions
def log_exception(log=logger, message="Exception caught!"):
    log.debug(message + "\n" + traceback.format_exc())


def to_unicode(x, default_encoding=None):
    """Force getting a unicode string from any object."""
    if isinstance(x, unicode):
        return x
    elif default_encoding and isinstance(x, str):
        # This unicode constructor only accepts "string or buffer".
        return unicode(x, default_encoding)
    else:
        return unicode(x)

def threaded(f):
    """
        A decorator that will make any function run in a new thread
    """
    
    # TODO: make this bad hack unneeded
    if _TESTING: return f
    @wraps(f)
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=f, args=args, kwargs=kwargs)
        t.setDaemon(True)
        t.start()

    return wrapper

def synchronized(func):
    """
        A decorator to make a function synchronized - which means only one
        thread is allowed to access it at a time
    """
    @wraps(func)
    def wrapper(self,*__args,**__kw):
        try:
            rlock = self._sync_lock
        except AttributeError:
            from threading import RLock
            rlock = self.__dict__.setdefault('_sync_lock',RLock())
        rlock.acquire()
        try:
            return func(self,*__args,**__kw)
        finally:
            rlock.release()
    return wrapper


# this code stolen from listen-gnome
""" Parse a date and return a time object """
""" Date like  Thu, 02 02 2005 10:25:21 ... """
def strdate_to_time(date):
    #removing timezone
    c = date[-5:-4]
    if (c == '+') or (c == '-'):
        date = date[:-6]

    #FIXME : don't remove use it in strptime
    c = date[-3:]
    if c in ["GMT","CST","EST","PST","EDT","PDT"]:
        date = date[:-3]

    #Remove day because some field have incorrect string
    c = date.rfind(",")
    if c!=-1:
        date = date [c+1:]
    date = date.strip()

    #trying multiple date formats
    new_date = None

    #Set locale to C to parse date
    locale.setlocale(locale.LC_TIME, "C")

    formats = ["%d %b %Y %H:%M:%S",#without day, short month
                "%d %B %Y %H:%M:%S",#without day, full month
                "%d %b %Y",#only date , short month
                "%d %B %Y",#only date , full month
                "%b %d %Y %H:%M:%S",#without day, short month
                "%B %d %Y %H:%M:%S",#without day, full month
                "%b %d %Y",#only date , short month
                "%B %d %Y",#only date , full month
                "%Y-%m-%d %H:%M:%S",
                ]
    for format in formats:
        try:
            new_date = time.strptime(date,format)
        except ValueError:
            continue

    locale.setlocale(locale.LC_TIME, '')
    if new_date is None:
        return ""

    return time.mktime(new_date)

def escape_xml(text):
    """
        Replaces &, <, and > with their entity references
    """
    # Note: the order is important.
    table = [('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;')]
    for old, new in table:
        text = text.replace(old, new)
    return text

def local_file_from_url(url):
    """
        Returns a local file path based on a url. If you get strange errors,
        try running .encode() on the result
    """
    split = urlparse.urlsplit(url)
    return urlparse.urlunsplit(('', '') + split[2:])

class idict(dict): 
    """
        Case insensitive dictionary
    """
    def __init__(self): 
        """
            Initializes the dictionary
        """
        self.keys_dict = dict()
        dict.__init__(self)

    def __setitem__(self, item, val): 
        """
            Sets an item in the dict
        """
        if item is None: return
        dict.__setitem__(self, item.lower(), val)
        if hasattr(self, 'keys_dict'):
            self.keys_dict[item.lower()] = item
    
    def __getitem__(self, item): 
        """
            Gets an item from the dict
        """
        return dict.__getitem__(self, item.lower())

    def __contains__(self, key): 
        """
            Returns True if this dictionary contains the specified key
        """
        return self.has_key(key)

    def __delitem__(self, key=None):
        if key is None: return
        key = key.lower()
        dict.__delitem__(self, key)
        del self.keys_dict[key]

    def has_key(self, key): 
        """
            Returns True if this dictionary contains the specified key
        """
        if key is None:
            return False
        return dict.has_key(self, key.lower())

    def keys(self): 
        """
            Returns the case sensitive values of the keys
        """
        return self.keys_dict.values()

from UserDict import DictMixin
class odict(DictMixin):
    """
        An dictionary which keeps track
        of the order of added items

        Cherrypicked from http://code.activestate.com/recipes/496761/
    """
    def __init__(self, data=None, **kwdata):
        self._keys = []
        self._data = {}

        if data is not None:
            if hasattr(data, 'items'):
                items = data.items()
            else:
                items = list(data)
            for i in xrange(len(items)):
                length = len(items[i])
                if length != 2:
                    raise ValueError('dictionary update sequence element '
                        '#%d has length %d; 2 is required' % (i, length))
                self._keys.append(items[i][0])
                self._data[items[i][0]] = items[i][1]
        if kwdata:
            self._merge_keys(kwdata.iterkeys())
            self.update(kwdata)
        
    def __setitem__(self, key, value):
        if key not in self._data:
            self._keys.append(key)
        self._data[key] = value
        
    def __getitem__(self, key):
        return self._data[key]
    
    def __delitem__(self, key):
        del self._data[key]
        self._keys.remove(key)

    def __repr__(self):
        result = []
        for key in self._keys:
            result.append('(%s, %s)' % (repr(key), repr(self._data[key])))
        return ''.join(['OrderedDict', '([', ', '.join(result), '])'])

    def __iter__(self):
        for key in self._keys:
            yield key

    def _merge_keys(self, keys):
        self._keys.extend(keys)
        newkeys = {}
        self._keys = [newkeys.setdefault(x, x) for x in self._keys
            if x not in newkeys]

    def update(self, data):
        if data is not None:
            if hasattr(data, 'iterkeys'):
                self._merge_keys(data.iterkeys())
            else:
                self._merge_keys(data.keys())
            self._data.update(data)
        
    def keys(self):
        return list(self._keys)
    
    def copy(self):
        copyDict = odict()
        copyDict._data = self._data.copy()
        copyDict._keys = self._keys[:]
        return copyDict

def random_string(n):
    """
        returns a random string of length n, comprised of ascii characters
    """
    s = ""
    for i in xrange(n):
        s += random.choice(string.ascii_letters)
    return s

def the_cutter(field):
    """
        Cuts "the"-like words off of the beginning of any field for better
        sorting
    """
    lowered = field.lower()
    for word in ("el ", "l'", "la ", "le ", "les ", "los ", "the "):
        if lowered.startswith(word):
            field = field[len(word):]
            break
    return field

def lstrip_special(field, cutter=False):
    """
        Strip special chars off the beginning of a field for sorting. If
        stripping the chars leaves nothing the original field is returned with
        only whitespace removed.
    """
    if field == None:
        return field
    lowered = field.lower()
    stripped = lowered.lstrip(" `~!@#$%^&*()_+-={}|[]\\\";'<>?,./")
    if stripped:
        ret = stripped
    else:
        ret = lowered.lstrip()
    if cutter:
        ret = the_cutter(ret)
    
    return ret

class VersionError(Exception):
    """
       Represents version discrepancies
    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)

# vim: et sts=4 sw=4

