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
import pygtk
pygtk.require('2.0')
import gtk, gtk.glade
import locale, time, threading, urllib

# python<2.5 compatibility. Drop this when python2.4 isn't used so much anymore.
try:
    any = any
except NameError:
    def any(seq):
        for e in seq:
            if e: return True
        return False

class MultiTextEntryDialog(gtk.Dialog):
    """
        Exactly like a TextEntryDialog, except it can contain multiple
        labels/fields.

        Instead of using GetValue, use GetValues.  It will return a list with
        the contents of the fields. Each field must be filled out or the dialog
        will not close.
    """
    def __init__(self, parent, title):
        gtk.Dialog.__init__(self, title, parent)


        self.hbox = gtk.HBox()
        self.vbox.pack_start(self.hbox, True, True)
        self.vbox.set_border_width(5)
        self.hbox.set_border_width(5)
        self.left = gtk.VBox()
        self.right = gtk.VBox()

        self.hbox.pack_start(self.left, True, True)
        self.hbox.pack_start(self.right, True, True)

        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OK, gtk.RESPONSE_OK)

        self.fields = []

    def add_field(self, label):
        """
            Adds a field and corresponding label
        """
        label = gtk.Label(label + "     ")
        label.set_alignment(0, 0)
        label.set_padding(0, 5)
        self.left.pack_start(label, False, False)

        entry = gtk.Entry()
        entry.connect('activate', lambda *e:
            self.response(gtk.RESPONSE_OK))
        entry.set_width_chars(30)
        self.right.pack_start(entry, True, True)
        label.show()
        entry.show()

        self.fields.append(entry)

    def get_values(self):
        """
            Returns a list of the values from the added fields
        """
        return [a.get_text() for a in self.fields]

    def run(self):
        """
            Shows the dialog, runs, hides, and returns
        """
        self.show_all()
        response = gtk.Dialog.run(self)
        self.hide()
        return response

class TextEntryDialog(gtk.Dialog):
    """
        Shows a dialog with a single line of text
    """
    def __init__(self, parent, message, title):
        """
            Initializes the dialog
        """
        gtk.Dialog.__init__(self, title, parent)

        label = gtk.Label(message)
        label.set_alignment(0.0, 0.0)
        self.vbox.set_border_width(5)

        main = gtk.VBox()
        main.set_spacing(3)
        main.set_border_width(5)
        self.vbox.pack_start(main, True, True)

        main.pack_start(label, False, False)

        self.entry = gtk.Entry()
        self.entry.set_width_chars(35)
        main.pack_start(self.entry, False, False)

        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OK, gtk.RESPONSE_OK)

        self.entry.connect('activate', 
            lambda e: self.response(gtk.RESPONSE_OK))

    def get_value(self):
        """
            Returns the text value
        """
        return self.entry.get_text()

    def set_value(self, value):
        """
            Sets the value of the text
        """
        self.entry.set_text(value)

    def run(self):
        self.show_all()
        response = gtk.Dialog.run(self)
        self.hide()
        return response

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
    try:
        return 'file://' + urllib.pathname2url(path)
    except IOError:
        return path

class ScrolledMessageDialog(gtk.Dialog):
    def __init__(self, parent, title):
        gtk.Dialog.__init__(self, title, parent)

        main = gtk.VBox()
        main.set_border_width(5)
        self.vbox.pack_start(main, True, True)

        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OK, gtk.RESPONSE_OK)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.view = gtk.TextView()
        self.view.set_editable(False)
        scroll.add(self.view)

        main.pack_start(scroll, True, True)
        self.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.resize(500, 300)

    def run(self):
        self.show_all()
        response = gtk.Dialog.run(self)
        self.hide()
        return response

def scrolledMessageDialog(parent, message, title):
    """
        Shows a message dialog with a message in a TextView
    """
    dialog = ScrolledMessageDialog(parent, title, message)
    view = dialog.view
    view.get_buffer().set_text(message)

    buf = view.get_buffer()
    char = buf.get_char_count()
    iter = buf.get_iter_at_offset(char)
    view.scroll_to_iter(iter, 0)
    dialog.run()

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

class ShowOnceMessageDialog(gtk.Dialog):
    def __init__(self, title, parent, message, checked=True):
        gtk.Dialog.__init__(self, title, parent)

        vbox = gtk.VBox()
        vbox.set_border_width(5)
        vbox.set_spacing(3)
        self.vbox.pack_start(vbox, True, True)

        top = gtk.HBox()
        top.set_border_width(3)
        top.set_spacing(5)
        top.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_WARNING,
            gtk.ICON_SIZE_DIALOG), False, False)
        label = gtk.Label()
        label.set_markup('<b>%s</b>' % message)
        label.set_alignment(0.0, 0.5)
        top.pack_start(label, True, True)

        vbox.pack_start(top, True, True)

        # TRANSLATORS: Checkbox for common dialogs
        self.box = gtk.CheckButton(_('Do not show this dialog again'))
        self.box.set_active(checked)
        vbox.pack_start(self.box)

        self.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK)

    def run(self):
        self.show_all()
        result = gtk.Dialog.run(self)
        self.hide()
        return self.box.get_active()

