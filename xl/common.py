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

from gettext import gettext as _
import locale, os, time, threading, urllib, re
import traceback

VALID_TAGS = (
    # Ogg Vorbis spec tags
    "title version album tracknumber artist genre performer copyright "
    "license organization description location contact isrc date "

    # Other tags we like
    "arranger author composer conductor lyricist discnumber labelid part "
    "website language encodedby bpm albumartist originaldate originalalbum "
    "originalartist recordingdate"
    ).split()

def get_default_encoding():
    return 'utf-8'

def log(message):
    print message

def log_exception(*e):
    traceback.print_exc()

# python<2.5 compatibility. Drop this when python2.4 isn't used so much anymore.
try:
    any = any
except NameError:
    def any(seq):
        for e in seq:
            if e: return True
        return False

def to_unicode(x, default_encoding=None):
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
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=f, args=args, kwargs=kwargs)
        t.setDaemon(True)
        t.start()

    wrapper.__name__ = f.__name__
    wrapper.__dict__ = f.__dict__
    wrapper.__doc__ = f.__doc__

    return wrapper

def synchronized(func):
    """
        A decorator to make a function synchronized - which means only one
        thread is allowed to access it at a time
    """
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
    wrapper.__name__ = func.__name__
    wrapper.__dict__ = func.__dict__
    wrapper.__doc__ = func.__doc__
    return wrapper

class idict(dict): 
    """
        Case insensitive dictionary
    """
    def __init__(self): 
        """
            Initializes the dictionary
        """
        dict.__init__(self)
        self.keys_dict = dict()
    

    def __setitem__(self, item, val): 
        """
            Sets an item in the dict
        """
        dict.__setitem__(self, item.lower(), val)
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
    

    def has_key(self, key): 
        """
            Returns True if this dictionary contains the specified key
        """
        return dict.has_key(self, key.lower())
    

    def keys(self): 
        """
            Returns the case sensitive values of the keys
        """
        return self.keys_dict.values()
    
class ldict(dict):
    """
        A dict that only handles lists
    """
    def __init__(self):
        dict.__init__(self)

    def __setitem__(self, item, value):
        if type(value) is not list: value = [value]
        dict.__setitem__(self, item , value)

    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            return []

class ilist(list): 
    """
        Case insensitive list
    """
    def __init__(self): 
        """
            Initializes the list
        """
        list.__init__(self)
    

    def __contains__(self, item): 
        """
            Returns true if this list contains the specified item
        """
        for i in self:
            if i.lower() == item.lower():
                return True

        return False



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

def to_url(path):
    """
        Converts filesystem path to URL. Returns the input unchanged if it's not
        an FS path (i.e. a URL or something invalid).
    """
    if re.search(r'^[\w]+://', path):
        return path
    try:
        return 'file://' + urllib.pathname2url(path)
    except IOError:
        return path


# Borrowed from Celerity with permission.
class SignalSender(object):
    """
        A simple signal implementation, mainly to avoid depending 
        on gobject
    """
    def __init__(self):
        self.__signals = {}

    def connect(self, signal, function):
        if self.__signals.has_key(signal):
            if function not in self.__signals[signal]:
                self.__signals[signal].append(function)
            else:
                pass # TODO: raise exception
        else:
            pass # TODO: raise exception

    def emit(self, signal):
        if self.__signals.has_key(signal):
            funcs = self.__signals[signal]
            for func in funcs:
                func.__call__(self)
        else:
            pass # TODO: raise an exception here

    def disconnect(self, signal, function):
        if self.__signals.has_key(signal):
            if function in self.__signals[signal]:
                self.__signals[signal].remove(function)
            else:
                pass # TODO: raise exception
        else:
            pass # TODO: raise exception

    def add_signal(self, signal):
        if not self.__signals.has_key(signal):
            self.__signals[signal] = []
        else:
            pass # TODO: raise exception here

    def remove_signal(self, signal):
        if self.__signals.has_key(signal):
            del self.__signals[signal]
        else:
            pass # TODO: raise exception here
