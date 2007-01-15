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


import sys, re
import pygtk
pygtk.require('2.0')
import gtk, gtk.glade
import locale, time, threading

def tup(string, num):
    """
        returns a tuple with the first char of the string repeated 
        the number of times after the first char:
        ie: 5e would result in ('e', 'e', 'e', 'e', 'e')
    """
    a = []
    for i in range(num):
        a.append(string)
    return tuple(a)

def threaded(f):
    def wrapper(*args):
        t = threading.Thread(target=f, args=args)
        t.setDaemon(True)
        t.start()

    return wrapper

def synchronized(func):
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

def scrolledMessageDialog(parent, message, title):
    """
        Shows a message dialog with a message in a TextView
    """
    xml = gtk.glade.XML('exaile.glade', 'ScrolledMessageDialog', 'exaile')
    dialog = xml.get_widget('ScrolledMessageDialog')
    dialog.set_title(title)
    view = xml.get_widget('smd_text_view')
    view.get_buffer().set_text(message)

    dialog.set_transient_for(parent)
    buf = view.get_buffer()
    char = buf.get_char_count()
    iter = buf.get_iter_at_offset(char)
    dialog.show_all()
    view.scroll_to_iter(iter, 0)
    dialog.run()
    dialog.destroy()

def error(parent, message): 
    """
        Shows an error dialog
    """
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_OK, message)
    dialog.run()
    dialog.destroy()

def info(parent, message):
    """
        Shows an info dialog
    """
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
        gtk.BUTTONS_OK, message)
    dialog.run()
    dialog.destroy()

def yes_no_dialog(parent, message):
    """
        Shows a question dialog and returns the result
    """
    dialog = gtk.MessageDialog(parent, 
        gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
        message)
    result = dialog.run()
    dialog.destroy()
    return result
