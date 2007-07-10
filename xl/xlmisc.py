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

"""
This file contains every miscellanious dialog and class that is not over
300 lines of code.  Once they read 300+ lines, they should be put into
their own file
"""

import httplib, os, re, sys, threading, time, traceback, urllib, urlparse
from gettext import gettext as _

import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk.gdk import SCROLL_LEFT, SCROLL_RIGHT, SCROLL_UP, SCROLL_DOWN

try:
    from xl import mozembed
except ImportError:
    mozembed = None

USE_TRAY = None
import warnings
warnings.filterwarnings('ignore', 'the module egg.trayicon is deprecated',
    DeprecationWarning)
try:
    import egg.trayicon
    USE_TRAY = 'egg'
except ImportError:
    if hasattr(gtk, 'StatusIcon'):
        USE_TRAY = 'gtk'

try:
    import sexy
    SEXY_AVAIL = True
except ImportError:
    SEXY_AVAIL = False


import common, prefs#, covers, media, prefs

opener = urllib.FancyURLopener()
opener.addheaders.pop(0)
opener.addheader("User-Agent","Mozilla")

def get_default_encoding():
    return 'utf-8'

class ClearEntry(object):
    """
        A gtk.Entry with a clear icon
    """
    def __init__(self, change_func):
        """
            Initializes the entry
        """
        self.sexy = SEXY_AVAIL
        if self.sexy:
            self.entry = sexy.IconEntry()
            image = gtk.Image()
            image.set_from_stock('gtk-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.entry.set_icon(sexy.ICON_ENTRY_SECONDARY, image)
            if change_func:
                self.entry.connect('icon-released', self.icon_released)
        else:
            self.entry = gtk.Entry()
        self.entry.connect('changed', change_func)

    def set_clear_callback(self, cb):
        """
            Sets the callback to be called after the clear button is pressed
        """
        self.clear_callback = cb

    def icon_released(self, *e):
        """
            Called when the user clicks the entry icon
        """
        self.entry.set_text('')

    def __getattr__(self, attr):
        """
            If this object doesn't have the attribute, check the gtk.Entry for
            it
        """
        if attr == 'entry': return self.entry
        return getattr(self.entry, attr)

def finish(repeat=True):
    """
        Waits for current pending gtk events to finish
    """
    while gtk.events_pending():
        gtk.main_iteration()
        if not repeat: break

class MmKeys:
    """
        Multimedia key grabber, using GNOME or the mmkeys module.

        Because of how the mmkeys module works, you must keep a reference to the
        instance of this class, specifically if the grabbing is done through
        mmkeys.
    """
    def __init__(self, application, callback):
        """
            Constructor.

            callback is a function that will be called with one of these as
            argument: 'Play', 'PlayPause', 'Pause', 'Stop', 'Previous', 'Next',
            or any future GNOME mmkey string.
        """
        self.application = application
        self.callback = callback

    def __del__(self):
        if self.use == 'gnome':
            try:
                self.__gnome.ReleaseMediaPlayerKeys(self.application)
            except:
                log_exception()

    def grab(self):
        """
            Try to grab multimedia keys.  Returns 'gnome', 'mmkeys', or None.
        """
        self.use = self.__use_gnome() or self.__use_mmkeys()
        return self.use

    def __use_gnome(self):
        def on_gnome_mmkey(app, key):
            if app == self.application:
                self.callback(key)

        try:
            import dbus
            bus = dbus.SessionBus()
            obj = bus.get_object('org.gnome.SettingsDaemon',
                '/org/gnome/SettingsDaemon')
            self.__gnome = gnome = dbus.Interface(obj,
                'org.gnome.SettingsDaemon')
            gnome.GrabMediaPlayerKeys(self.application, 0)
            gnome.connect_to_signal('MediaPlayerKeyPressed', on_gnome_mmkey)
        except:
            return None

        return 'gnome'

    def __use_mmkeys(self):
        try:
            import mmkeys
        except ImportError:
            return None

        # Must keep a reference to the object.
        self.__mmkeys = keys = mmkeys.MmKeys()
        keys.connect('mm_playpause', lambda e, f: self.callback('PlayPause'))
        keys.connect('mm_stop', lambda e, f: self.callback('Stop'))
        keys.connect('mm_prev', lambda e, f: self.callback('Previous'))
        keys.connect('mm_next', lambda e, f: self.callback('Next'))

        return 'mmkeys'

class Menu(gtk.Menu):
    """
        A proxy for making it easier to add icons to menu items
    """
    def __init__(self):
        """
            Initializes the menu
        """
        gtk.Menu.__init__(self)

        self.show()

    def append_image(self, pixbuf, callback, data=None):
        """
            Appends a graphic as a menu item
        """
        item = gtk.MenuItem()
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        item.add(image)
        
        if callback: item.connect('activate', callback, data)
        gtk.Menu.append(self, item)
        item.show_all()
        return item

    def append(self, label, callback, stock_id=None, data=None):
        """
            Appends a menu item
        """
        if stock_id:
            item = gtk.MenuItem()
            hbox = gtk.HBox()
            hbox.set_spacing(5)
            item.add(hbox)
            image = gtk.image_new_from_stock(stock_id,
                gtk.ICON_SIZE_MENU)
            hbox.pack_start(image, False, True)
            label = gtk.Label(label)
            label.set_alignment(0, 0)
            hbox.pack_start(label, True, True)
        else:
            item = gtk.MenuItem(label)
            self.label = item.get_child()

        if callback: item.connect('activate', callback, data)
        gtk.Menu.append(self, item)
        item.show_all()
        return item

    def append_item(self, item):
        """
            Appends a menu item
        """
        gtk.Menu.append(self, item)
        item.show_all()

    def append_menu(self, label, menu, stock_id=None):
        """
            Appends a submenu
        """
        if stock_id:
            item = self.append(label, None, stock_id)
            item.set_submenu(menu)
            return item

        item = gtk.MenuItem(label)
        item.set_submenu(menu)
        item.show()
        gtk.Menu.append(self, item)

        return item

    def insert_menu(self, index, label, menu):
        """
            Inserts a menu at the specified index
        """
        item = gtk.MenuItem(label)
        item.set_submenu(menu)
        item.show()
        gtk.Menu.insert(self, item, index)

        return item

    def append_separator(self):
        """
            Adds a separator
        """
        item = gtk.SeparatorMenuItem()
        item.show()
        gtk.Menu.append(self, item)

class Adjustment(gtk.Adjustment):
    """
        Custom adjustment with convenience functions
    """
    def decrease(self, diff):
        self.props.value -= diff
    def increase(self, diff):
        self.props.value += diff
    def page_down(self):
        self.props.value -= self.props.page_increment
    def page_up(self):
        self.props.value += self.props.page_increment
    def step_down(self):
        self.props.value -= self.props.step_increment
    def step_up(self):
        self.props.value += self.props.step_increment

def get_icon(id, size=gtk.ICON_SIZE_BUTTON):
    """
        Returns a stock icon for the specified id and size
    """
    theme = gtk.icon_theme_get_default()
    try:
        icon = theme.load_icon(id, size, gtk.ICON_LOOKUP_NO_SVG)
        if icon: return icon
    except gobject.GError:
        pass
    
    return gtk.gdk.pixbuf_new_from_file(os.path.join('images', 'default_theme',
        id + '.png'))

class BaseTrayIcon(gobject.GObject):
    """
        System tray icon
    """
    __gsignals__ = {
        'toggle-hide': (gobject.SIGNAL_RUN_LAST, bool, tuple())
    }
    def __init__(self, exaile):
        """
            Initializes the tray icon
        """
        gobject.GObject.__init__(self)
        self.exaile = exaile
        self.setup_menu()

    def setup_menu(self):
        """
            Sets up the popup menu for the tray icon
        """
        self.menu = Menu()

        self.image = gtk.Image()
        self.image.set_from_stock('gtk-media-play',
            gtk.ICON_SIZE_MENU)
        self.label = gtk.Label(_("Play"))
        self.label.set_alignment(0, 0)

        self.playpause = gtk.MenuItem()
        hbox = gtk.HBox()
        hbox.set_spacing(5)
        hbox.pack_start(self.image, False, True)
        hbox.pack_start(self.label, True, True)
        self.playpause.add(hbox)
        self.playpause.connect('activate', lambda *e: self.exaile.player.toggle_pause())
        self.menu.append_item(self.playpause)

        self.menu.append(_("Next"), lambda *e: self.exaile.player.next(), 'gtk-media-next')
        self.menu.append(_("Previous"), lambda *e: self.exaile.player.previous(),
            'gtk-media-previous')
        self.menu.append_separator()
        self.menu.append(_("Plugins"), self.exaile.show_plugin_manager,
            'gtk-execute')
        self.menu.append(_("Preferences"), 
            lambda e, a: prefs.Preferences(self.exaile).run(),
            'gtk-preferences')

        self.menu.append_separator()
        self.menu.append(_("Quit"), self.exaile.on_quit, 'gtk-quit')

    def update_menu(self):
        track = self.exaile.player.current
        if not track or not self.exaile.player.is_playing():
            self.image.set_from_stock('gtk-media-play',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Play"))
        elif self.exaile.player.is_playing():
            self.image.set_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Pause"))

    def toggle_exaile_visibility(self):
        w = self.exaile.window
        if w.is_active(): # focused
            if self.emit('toggle-hide'): return
            w.hide()
        elif w.get_property('visible'): # unfocused
            w.present()
        else: # hidden
            if self.emit('toggle-hide'): return
            w.present()
            self.exaile.setup_location()

    def set_tooltip(self, tip): # to be overridden
        """
            Sets the tooltip for the tray icon
        """
        pass

    def destroy(self): # to be overridden
        """
            Unhides the window and removes the tray icon

            The unhiding is done here, while the removal needs to be
            done in a subclass. Don't forget to call this superclass
            method when you override it.
        """
        self.emit('toggle-hide') # FIXME: should this be vetoable?
        if not self.exaile.window.get_property('visible'):
            self.exaile.window.present()
            self.exaile.setup_location()

class EggTrayIcon(BaseTrayIcon):
    def __init__(self, exaile):
        BaseTrayIcon.__init__(self, exaile)

        self.tips = gtk.Tooltips()
        self.icon = egg.trayicon.TrayIcon(_('Exaile'))
        self.box = gtk.EventBox()
        self.icon.add(self.box)

        image = gtk.Image()
        image.set_from_file(os.path.join('images', 'trayicon.png'))
        self.box.add(image)
        self.box.connect('button_press_event',
            self.button_pressed)
        self.box.connect('scroll-event',
            self.scroll)
        self.box.connect('enter-notify-event', lambda *e: 
            self.exaile.show_osd(tray=True))
        self.icon.show_all()
        self.set_tooltip(_("Exaile Media Player"))

    def scroll(self, widget, ev):
        """
            Called when the user scrolls their mouse wheel over the tray icon
        """
        if ev.direction in [SCROLL_LEFT, SCROLL_RIGHT]:
            ev.state = gtk.gdk.SHIFT_MASK
        if ev.state & gtk.gdk.SHIFT_MASK:
            if ev.direction in [SCROLL_UP, SCROLL_LEFT]: self.exaile.on_previous()
            elif ev.direction in [SCROLL_DOWN, SCROLL_RIGHT]: self.exaile.on_next()
        else:
            if ev.direction in [SCROLL_RIGHT, SCROLL_UP]:
                self.exaile.volume.page_up()
            else:
                self.exaile.volume.page_down()

    def button_pressed(self, item, event, data=None):
        """
            Called when someone clicks on the icon
        """
        if event.button == 3:
            self.update_menu()
            self.menu.popup(None, None, None, event.button, event.time)
        elif event.button == 2:
            self.exaile.toggle_pause()
        elif event.button == 1: 
            self.toggle_exaile_visibility()

    def set_tooltip(self, tip):
        self.tips.set_tip(self.icon, tip)

    def destroy(self):
        BaseTrayIcon.destroy(self)
        self.icon.destroy()

class GtkTrayIcon(BaseTrayIcon):
    def __init__(self, exaile):
        BaseTrayIcon.__init__(self, exaile)
        self.icon = icon = gtk.StatusIcon()
        icon.set_tooltip(_('Exaile'))
        icon.set_from_file(os.path.join('images', 'trayicon.png'))
        icon.connect('activate', self.activated)
        icon.connect('popup-menu', self.popup)
        self.set_tooltip(_("Exaile Music Player"))

    def activated(self, icon):
        self.toggle_exaile_visibility()

    def popup(self, icon, button, time):
        self.update_menu()
        self.menu.popup(None, None, gtk.status_icon_position_menu,
            button, time, self.icon)

    def set_tooltip(self, tip):
        self.icon.set_tooltip(tip)

    def destroy(self):
        BaseTrayIcon.destroy(self)
        self.icon.set_visible(False)

if USE_TRAY == 'egg':
    TrayIcon = EggTrayIcon
elif USE_TRAY == 'gtk':
    TrayIcon = GtkTrayIcon
else:
    TrayIcon = None

class ListBox(object):
    """
        Represents a list box
    """
    def __init__(self, widget, rows=None):
        """
            Initializes the widget
        """
        self.list = widget
        self.store = gtk.ListStore(gobject.TYPE_STRING)
        widget.set_headers_visible(False)
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('', cell, text=0)
        self.list.append_column(col)
        self.rows = rows
        if not rows: self.rows = []
        
        if rows:
            for row in rows:
                self.store.append([row])

        self.list.set_model(self.store)

    def connect(self, signal, func, data=None):
        """
            Connects a signal to the underlying treeview
        """
        self.list.connect(signal, func, data)

    def append(self, row):
        """
            Appends a row to the list
        """
        self.rows.append(row)
        self.set_rows(self.rows)

    def remove(self, row):
        """
            Removes a row
        """
        if not row in self.rows: return
        index = self.rows.index(row)
        path = (index,)
        iter = self.store.get_iter(path)
        self.store.remove(iter)
        self.rows.remove(row)

    def set_rows(self, rows):
        """
            Sets the rows
        """
        self.rows = rows
        self.store = gtk.ListStore(gobject.TYPE_STRING)
        for row in rows:
            self.store.append([row])

        self.list.set_model(self.store)

    def get_selection(self):
        """
            Returns the selection
        """
        selection = self.list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter: return None
        return model.get_value(iter, 0)

gtk.rc_parse_string("""
    style "thinWidget" {
        xthickness = 0
        ythickness = 0
    }
    widget "*.tabCloseButton" style "thinWidget"
    """)
class NotebookTab(gtk.EventBox):
    """
        Shows a close image on a notebook tab
    """

    def __init__(self, exaile, title, page):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.connect('button_press_event', self.on_button_press)
        
        self.exaile = exaile
        self.title = title
        self.page = page
        self.nb = exaile.playlists_nb
        self.tips = gtk.Tooltips()
        
        self.hbox = hbox = gtk.HBox(False, 5)
        self.add(hbox)
        
        self.label = gtk.Label(title)
        hbox.pack_start(self.label, False, False)
        
        self.button = btn = gtk.Button()
        btn.set_name('tabCloseButton')
        btn.set_relief(gtk.RELIEF_NONE)
        btn.set_focus_on_click(False)
        btn.connect('clicked', self.do_close)
        btn.connect('button_press_event', self.on_button_press)
        self.tips.set_tip(btn, _("Close this tab"))
        image = gtk.Image()
        image.set_from_stock('gtk-close', gtk.ICON_SIZE_MENU)
        btn.add(image)
        hbox.pack_end(btn, False, False)
        
        self.show_all()

    def rename(self, widget, event):
        """
            Renames the tab
        """
        dialog = common.TextEntryDialog(self.exaile.window, 
            _("Enter the new name for this playlist"), _("Rename playlist"))
        if dialog.run() == gtk.RESPONSE_OK:
            name = dialog.get_value()
            self.title = name
            self.label.set_label(name)
        dialog.destroy()

    def save_playlist(self, widget, event):
        """
            Saves a playlist
        """
        songs = self.page.songs
        self.exaile.playlists_panel.on_add_playlist(widget, None, songs)

    def do_close(self, *args):
        """
            Closes the tab
        """
        self.exaile.close_page(self.page)

    def create_menu(self):
        """
            Creates the popup menu for this tab
        """
        menu = Menu()
        if self.page.type == 'track':
            menu.append(_("Rename"), self.rename)
        menu.append(_("Close"), self.do_close)

        if self.page.type == 'track':
            menu.append(_("Save Playlist"), self.save_playlist)
            
        self.menu = menu

    def on_button_press(self, widget, event):
        """
            Shows menu when user right-clicks on tab
        """
        if event.button == 3:
            self.create_menu()
            self.menu.popup(None, None, None, event.button, event.time)
        return False

class DebugDialog(object):
    """
        A window to show debug messages
    """
    debug = None
    
    def __init__(self, parent):
        """
            Initializes the dialog
        """
        self.exaile = parent
        xml = gtk.glade.XML('exaile.glade', 'DebugDialog', 'exaile')
        self.dialog = xml.get_widget('DebugDialog')
        self.dialog.set_transient_for(self.exaile.window)
        self.view = xml.get_widget('debug_textview')
        self.buf = self.view.get_buffer()
        self.log_file = None
        xml.get_widget('debug_ok_button').connect('clicked', 
            lambda *e: self.dialog.hide())
        self.dialog.connect('delete_event', self.destroy)
        
        DebugDialog.debug = self

    def destroy(self, *e):
        """
            Called when the users clicks on the close button
        """
        self.dialog.hide()
        return True

    def log(self, message, timestamp=None):
        """ 
            Logs a message
        """

        if not timestamp: timestamp = time.time()
        lt = time.localtime(timestamp)
        text = "[%s] %s\n" % (time.strftime("%H:%M:%S", lt), message)
        char = self.buf.get_char_count()
        iter = self.buf.get_iter_at_offset(char + 1)

        self.buf.insert(iter, text)
        print message
        if not self.log_file:
            try:
                self.log_file = open(self.exaile.get_settings_dir() + os.sep +
                    "exaile.log", 'a')
            except:
                self.log_file = None

        if self.log_file:
            self.log_file.write(text)
            self.log_file.flush()

        char = self.buf.get_char_count()
        iter = self.buf.get_iter_at_offset(char + 1)
        self.view.scroll_to_iter(iter, 0)

    def __del__(self):
        """
            Closes the log file
        """

        if self.log_file:
            self.log_file.close()

LOG_QUEUE = dict()
def log(message):
    """
        Queues a log event
    """
    gobject.idle_add(__log, message)

def __log(message):
    """
        If the log dialog has not been initialized, it adds the message to a
        queue to be added later, else it logs it to the debug dialog
    """
    dialog = DebugDialog.debug

    if not dialog:
        if media.exaile_instance:
            DebugDialog(media.exaile_instance)
        LOG_QUEUE[time.time()] = message
    else:
        if LOG_QUEUE:
            keys = LOG_QUEUE.keys()
            keys.sort()
            for key in keys:
                dialog.log(LOG_QUEUE[key], key)
            LOG_QUEUE.clear()

        dialog.log(message)

def log_exception():
    """
        Queues a log event
    """
    message = log_file_and_line() + traceback.format_exc()
    gobject.idle_add(__log_exception, message)

def __log_exception(message):
    """
        Logs an exception
    """
    message = message.split("\n")
    for line in message:
        log(line)

def log_file_and_line():
    """
       Logs where we are (function, file name and line number)
       when log_exception is called... handy for debugging.
    """
    co = sys._getframe(2).f_code
    return "-----------------------\n" \
           " %s ( %s @ %s):\n" \
           "-----------------------\n" % (co.co_name, co.co_filename, co.co_firstlineno)

class URLFetcher(threading.Thread):
    """
        Fetches information from a URL
    """
    def __init__(self, server, path, done_func):
        """
            Initializes the thread
        """
        threading.Thread.__init__(self)
        self.server = server 
        self.path = path 

        print self.server, self.path
        self.setDaemon(True)
        self.done_func = done_func

    def run(self):
        """
            Called by thread.start()
        """

        conn = httplib.HTTPConnection(self.server)

        conn.request("GET", self.path)
        response = conn.getresponse()

        if response.status != 200:
            self.notify("Could not load page. "
                "Error %d: %s" % 
                (response.status, response.reason))
            return

        page = response.read()
        self.notify(page)

    def notify(self, text):
        """
            Calls the done_func after the current gtk pending event
        """
        gobject.idle_add(self.done_func, self.server + self.path, text)

class BrowserWindow(gtk.VBox):
    """
        An HTML window for Wikipedia information
    """
    def __init__(self, exaile, url, nostyles=False):
        """
            Initializes the window
        """
        gtk.VBox.__init__(self)
        self.set_border_width(5)
        self.set_spacing(3)
        self.nostyles = nostyles
        self.action_count = 0

        self.exaile = exaile
        if not nostyles:
            top = gtk.HBox()
            top.set_spacing(3)

            self.back = gtk.Button()
            image = gtk.Image()
            image.set_from_stock('gtk-go-back', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.back.set_image(image)
            self.back.set_sensitive(False)
            self.back.connect('clicked', self.on_back)
            top.pack_start(self.back, False, False)

            self.next = gtk.Button()
            image = gtk.Image()
            image.set_from_stock('gtk-go-forward', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.next.set_image(image)
            self.next.connect('clicked', self.on_next)
            self.next.set_sensitive(False)
            top.pack_start(self.next, False, False)

            w = gtk.Button(_("Open Browser"))
            w.connect('clicked', self.on_open_browser)
            top.pack_start(w, False, False)

            self.entry = gtk.Entry()
            self.entry.connect('activate', self.entry_activate)
            top.pack_start(self.entry, True, True)
            self.pack_start(top, False, True)

        self.view = mozembed.MozClient()
        self.pack_start(self.view, True, True)
        if not nostyles:
            self.view.connect('location', self.on_location_change)

        self.show_all()
        finish()

        self.view.set_data('<html><body><b>' + _('Loading requested'
            ' information...') + '</b></body></html>', '')
        exaile.status.set_first(_('Loading page...'))
        self.view.connect('net-stop', self.on_net_stop)

        self.cache_dir = os.path.join(exaile.get_settings_dir(), 'cache')

        self.server = ''

        if url:
            self.load_url(url, self.action_count, False)

    def on_net_stop(self, *args):
        """
            Called when mozilla is done loading the page
        """
        self.exaile.status.set_first(None)

    def set_text(self, text):
        """
            Sets the text of the browser window

        """
        self.view.set_data(text, '')

    def entry_activate(self, *e):
        """
            Called when the user presses enter in the address bar
        """
        url = self.entry.get_text()
        self.load_url(url, self.action_count)

    def on_location_change(self, mozembed):
        # Only called when not self.nostyles
        self.entry.set_text(mozembed.get_location())
        self.back.set_sensitive(self.view.can_go_back())
        self.next.set_sensitive(self.view.can_go_forward())

    def on_next(self, widget):
        """
            Goes to the next entry in history
        """
        self.view.go_forward()
            
    def on_back(self, widget):
        """
            Goes to the previous entry in history
        """
        self.view.go_back()

    def on_open_browser(self, button):
        """
            Opens the current URL in a new browser window (if possible).
        """
        # This method is rarely used, so we only do the import when we need to.
        import webbrowser
        # "new=1" is to request new window.
        webbrowser.open(self.view.get_location(), new=1)

    def load_url(self, url, action_count, history=False):
        """
            Loads a URL, either from the cache, or from the website specified
        """

        self.view.load_url(url)

        if not self.nostyles:
            if self.view.can_go_back(): self.back.set_sensitive(True)
            if not self.view.can_go_forward(): self.next.set_sensitive(False)
            self.entry.set_sensitive(True)
            self.entry.set_text(url)

class AboutDialog(gtk.Dialog):
    """
        An about dialog
    """

    def __init__(self, parent, version):
        """
            Initializes the dialog
        """
        xml = gtk.glade.XML('exaile.glade', 'AboutDialog', 'exaile')
        self.dialog = xml.get_widget('AboutDialog')
        logo = gtk.gdk.pixbuf_new_from_file(os.path.join('images',
            'exailelogo.png'))
        self.dialog.set_logo(logo)
        self.dialog.set_version(str(version))
        self.dialog.set_transient_for(parent)
        self.dialog.run()
        self.dialog.destroy()

class ImageWidget(gtk.Image):
    """
        Custom resizeable image widget
    """
    __gsignals__ = {
        'image-changed': (gobject.SIGNAL_RUN_LAST, 
            gobject.TYPE_NONE, (str,))
    }

    def __init__(self):
        """
            Initializes the image
        """
        gtk.Image.__init__(self)
        self.loc = ''

    def set_image_size(self, width, height):
        """
            Scales the size of the image
        """
        self.size = (width, height)

    def set_image(self, image, fill=False):
        """
            Sets the image
        """
        self.loc = image
        pixbuf = gtk.gdk.pixbuf_new_from_file(image)
        width, height = self.size
        if not fill:
            origw = float(pixbuf.get_width())
            origh = float(pixbuf.get_height())
            scale = min(width / origw, height / origh)
            width = int(origw * scale)
            height = int(origh * scale)
        self.width = width
        self.height = height
        scaled = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        self.set_from_pixbuf(scaled)

        scaled = pixbuf = None
        self.emit('image-changed', image)

class StatusBar(object):
    """
        A Custom status bar... allows for any component to be added to the
        status bar
    """
    def __init__(self, exaile):
        """
            Initializes the status bar
        """
        self.exaile = exaile
        self.xml = exaile.xml
        self.first_label = self.xml.get_widget('status_pos_1')
        self.second_label = self.xml.get_widget('status_pos_2')
        self.track_count_label = self.xml.get_widget('track_count_label')

    def set_track_count(self, count):
        """
            Sets the track count label
        """
        self.track_count_label.set_label(count)

    def clear(self):
        """
            Clears the text in the first section of the status bar
        """
        self.set_first(None)
        return False

    def set_first(self, text, time=0):
        """
            Sets the text in the first section of the status bar.  If time
            is specified, this text will be cleared after that amount of
            time (in milliseconds) has elapsed.
        """
        
        if not text:
            self.first_label.set_label('')

        else:
            self.first_label.set_label(text)

        if time:
            gobject.timeout_add(time, self.clear)

BITMAP_CACHE = dict()
def get_text_icon(widget, text, width, height, bgcolor='#456eac',   
    bordercolor=None):
    """
        Gets a bitmap icon with the specified text, width, and height
    """
    if BITMAP_CACHE.has_key("%s - %sx%s - %s" % (text, width, height, bgcolor)):
        return BITMAP_CACHE["%s - %sx%s - %s" % (text, width, height, bgcolor)]

    default_visual = gtk.gdk.visual_get_system()
    pixmap = gtk.gdk.Pixmap(None, width, height, default_visual.depth)
    colormap = gtk.gdk.colormap_get_system()
    white = colormap.alloc_color(65535, 65535, 65535)
    black = colormap.alloc_color(0, 0, 0)
    pixmap.set_colormap(colormap)
    gc = pixmap.new_gc(foreground=black, background=white)

    if not bordercolor: bordercolor = black
    else: 
        bordercolor = colormap.alloc_color(gtk.gdk.color_parse(bordercolor))
    gc.set_foreground(bordercolor)

    pixmap.draw_rectangle(gc, True, 0, 0, width, height)
    fg = colormap.alloc_color(gtk.gdk.color_parse(bgcolor))
    gc.set_foreground(fg)
    pixmap.draw_rectangle(gc, True, 1, 1, width - 2, height - 2)

    layout = widget.create_pango_layout(str(text))
    desc = pango.FontDescription("Bitstream Vera Sans 8")
    layout.set_font_description(desc)
    layout.set_alignment(pango.ALIGN_RIGHT)

    gc.set_foreground(white)
    inkRect, logicalRect = layout.get_pixel_extents()
    l, b, w, h = logicalRect
    x = ((width) / 2 - w / 2)
    y = ((height) / 2 - h / 2)
    pixmap.draw_layout(gc, x, y, layout)

    pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, width, height)
    pixbuf = pixbuf.get_from_drawable(pixmap, colormap, 0, 0, 0,
        0, width, height)

    BITMAP_CACHE["%s - %sx%s - %s" % (text, width, height, bgcolor)] = pixbuf
    return pixbuf


class MiscTimer(object):
    """
        Creates a timer that executes a function
    """
    def __init__(self, func, time, runonce=False):
        """
            Expects the function to call.  If runonce is True, the
            timer only runs one time
        """
        self.func = func
        self.time = time
        self.runonce = runonce
        self.connect_id = None

    def start(self):
        """
            Starts the timer
        """
        self.connect_id = gobject.timeout_add(self.time, self.notify)

    def stop(self):
        """
            Stops the timer
        """
        if not self.connect_id: return
        gobject.source_remove(self.connect_id)
        self.connect_id = None

    def notify(self):
        """
            Called when the timer time has elapsed
        """
        self.func()
        if self.runonce: return False
        else: return True

class OSDWindow(object):
    """
        A popup window to show information on the current playing track
    """
    def __init__(self, exaile, settings, start_timer=True, draggable=False):
        """
            Initializes the popup
        """
        self.exaile = exaile
        self.draggable = draggable
        self.xml = gtk.glade.XML('exaile.glade', 'OSDWindow', 'exaile')
        self.window = self.xml.get_widget('OSDWindow')
        self.__timeout = None
        self.start_timer = start_timer

        color = gtk.gdk.color_parse(settings['osd/bgcolor'])
        self.settings = settings
        self.event = self.xml.get_widget('popup_event_box')
        self.box = self.xml.get_widget('image_box')
        self.window.modify_bg(gtk.STATE_NORMAL, color)
        self.title = self.xml.get_widget('popup_title_label')

        self.window.set_size_request(settings['osd/w'], settings['osd/h'])
        self.cover = ImageWidget()
        self.box.pack_start(self.cover, False, False)
        self.window.move(settings['osd/x'], settings['osd/y'])
        self.cover.set_image_size(settings['osd/h'] - 8, settings['osd/h'] - 8)
        self.event.connect('button_press_event', self.start_dragging)
        self.event.connect('button_release_event', self.stop_dragging)
        self.__handler = None

    def start_dragging(self, widget, event):
        """
            Called when the user starts dragging the window
        """
        if not self.draggable:
            self.window.hide()
            return
        self.__start = event.x, event.y
        self.__handler = self.window.connect('motion_notify_event',
            self.dragging)
        if self.__timeout: gobject.source_remove(self.__timeout)
        self.__timeout = None

    def stop_dragging(self, widget, event):
        """
            Called when the user stops dragging the mouse
        """
        global POPUP
        if self.__handler: self.window.disconnect(self.__handler)
        self.__handler = None
        if self.start_timer:
            self.__timeout = gobject.timeout_add(4000, self.window.hide)
        settings = self.exaile.settings
        (w, h) = self.window.get_size()
        (x, y) = self.window.get_position()

        settings['osd/x'] = x
        settings['osd/y'] = y
        settings['osd/h'] = h
        settings['osd/w'] = w
    
        POPUP = OSDWindow(self.exaile, get_osd_settings(settings))

    def dragging(self, widget, event):
        """
            Called when the user drags the window
        """
        self.window.move(int(event.x_root - self.__start[0]),
            int(event.y_root - self.__start[1]))

    def show_track_osd(self, track, text, cover):
        """
            Shows a popup specific to a track
        """
        text = text.replace("&", "&amp;") # we don't allow entity refs here

        for item in ('title', 'artist', 'album', 'length', 'track', 'bitrate',
            'genre', 'year', 'rating'):
            try:
                value = getattr(track, item)
            except AttributeError:
                continue
            if not isinstance(value, basestring):
                value = unicode(value)
            text = text.replace("{%s}" % item, common.escape_xml(value))

        text = text.replace("{volume}", "%d%%" %
            self.exaile.get_volume_percent())
        text = text.replace("\\{", "{")
        text = text.replace("\\}", "}")
        self.show_osd(text, cover)

    def show_osd(self, title, cover):
        """
            Displays the popup for 4 seconds
        """
        if self.__timeout:
            gobject.source_remove(self.__timeout)
            self.window.hide()
        
        text = "<span font_desc='%s' foreground='%s'>%s</span>" % \
            (self.settings['osd/text_font'], self.settings['osd/text_color'],
            title)
        self.title.set_markup(text)

        if cover == None:
            cover = os.path.join('images', 'nocover.png')

        self.cover.set_image(cover)
        self.window.show_all()

        if self.start_timer: 
            self.__timeout = gobject.timeout_add(4000, self.window.hide)

POPUP = None
def get_osd(exaile, settings):
    """
        Gets a popup instance
    """
    global POPUP
    
    if not POPUP:
        POPUP = OSDWindow(exaile, settings)

    return POPUP

def get_osd_settings(settings):
    info = dict()
    info['osd/bgcolor'] = settings.get_str("osd/bgcolor", "#567ea2")
    info['osd/w'] = settings.get_int("osd/w", 400)
    info['osd/h'] = settings.get_int("osd/h", 95)
    info['osd/y'] = settings.get_int("osd/y", 0)
    info['osd/x'] = settings.get_int("osd/x", 0)
    info['osd/display_text'] = settings.get_str('osd/display_text', 
        prefs.TEXT_VIEW_DEFAULT)
    info['osd/text_font'] = settings.get_str('osd/text_font',
        'Sans 10')
    info['osd/text_color'] = settings.get_str('osd/text_color',
        '#ffffff')

    return info

class DragTreeView(gtk.TreeView):
    """
        A TextView that does easy dragging/selecting/popup menu
    """
    def __init__(self, cont, receive=True, source=True):
        """
            Initializes the tree and sets up the various callbacks
        """
        gtk.TreeView.__init__(self)
        self.cont = cont

        self.targets = [("text/uri-list", 0, 0)]

        if source:
            self.drag_source_set(
                gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        if receive:
            self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT)
            self.connect('drag_data_received', 
                self.cont.drag_data_received)
        self.receive = receive
        self.dragging = False
        self.connect('drag_begin', self.drag_begin)
        self.connect('drag_end', self.drag_end)
        self.connect('drag_motion', self.drag_motion)
        self.connect('button_release_event', self.button_release)
        self.connect('button_press_event', self.button_press)

        if source:
            self.connect('drag_data_get', self.cont.drag_get_data)
            self.drag_source_set_icon_stock('gtk-dnd')

    def button_release(self, button, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.dragging: 
            self.dragging = False
            return True
        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True
        selection = self.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.get_path_at_pos(x, y)
        if not path: return False
        selection.unselect_all()
        selection.select_path(path[0])

    def drag_end(self, list, context):
        """
            Called when the dnd is ended
        """
        self.dragging = False
        self.unset_rows_drag_dest()
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

    def drag_begin(self, list, context):
        """
            Called when dnd is started
        """
        self.dragging = True

        context.drag_abort(gtk.get_current_event_time())
        selection = self.get_selection()
        if selection.count_selected_rows() > 1:
            self.drag_source_set_icon_stock('gtk-dnd-multiple')
        else: self.drag_source_set_icon_stock('gtk-dnd')
        return False

    def drag_motion(self, treeview, context, x, y, timestamp):
        """
            Called when a row is dragged over this treeview
        """
        if not self.receive:
            return
        self.enable_model_drag_dest(self.targets,
            gtk.gdk.ACTION_DEFAULT)
        info = treeview.get_dest_row_at_pos(x, y)
        if not info: return
        treeview.set_drag_dest_row(info[0], info[1])

    def button_press(self, button, event):
        """
            The popup menu that is displayed when you right click in the
            playlist
        """
        selection = self.get_selection()
        (x, y) = event.get_coords()
        x = int(x)
        y = int(y)
        path = self.get_path_at_pos(x, y)
        if not path: return True
            
        if event.button != 3: 
            if event.type == gtk.gdk._2BUTTON_PRESS:
                self.cont.button_press(button, event)

            if selection.count_selected_rows() <= 1: return False
            else: 
                if selection.path_is_selected(path[0]): 
                    if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        selection.unselect_path(path[0])
                    return True
                elif not event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    return True
                return False

        if not selection.count_selected_rows():
            selection.select_path(path[0])
        return self.cont.button_press(button, event)

PLAYLIST_EXTS = []

class PlaylistParser(object):
    def __init__(self, name, url=None):
        self.name = name
        self.url = []

        self.parse_file(url)

    def add_url(self, url, title=None, album=''):
        if not title: title=url
        try: 
            url = list(urlparse.urlsplit(url))
        except:
            pass

        if not url[0]:
            url[0] = 'file'

        item = {
            'url': url,
            'title': title,
            'album': album
        }
        self.url.append(item)

    def get_urls(self):
        return self.url

    def get_full(self):
        return [urlparse.urlunsplit(u) for u in self.url]

    def get_name(self):
        return self.name

    def parse_file(self, url):
        f = urllib.urlopen(url)
        try:
            return self._do_parse_file(f)
        finally:
            try:
                f.close()
            except:
                pass

    def _do_parse_file(self, file):
        raise NotImplementedError

    def _get_url_from_path(self, basedir, s):
        if not urlparse.urlsplit(s)[0]: # no scheme --> local path
            if not os.path.isabs(s): # relative path
                s = os.path.join(basedir, s)
            s = 'file://' + urllib.quote(s)
        return s

class M3UParser(PlaylistParser):
    PLAYLIST_EXTS.append('.m3u')
    REGEX = re.compile(r'#EXTINF:\d+,(.*?)[\r\n]+(.*?)[\r\n]+', re.DOTALL) 

    def _do_parse_file(self, file):
        # Read first line to see if this is extended M3U.
        firstline = file.readline()
        if firstline.strip() == "#EXTM3U":
            return self._do_parse_extended(file)

        basedir = os.path.dirname(file.url)
        for line in [firstline] + file.readlines():
            line = line.strip()
            if line and line[0] == "#":
                url = self._get_url_from_path(basedir, line)
                self.add_url(url)

        return True

    def _do_parse_extended(self, file):
        data = file.read()
        items = self.REGEX.findall(data)
        if items:
            basedir = os.path.dirname(file.url)
            for item in items:
                url = self._get_url_from_path(basedir, item[1])
                self.add_url(url, title=item[0], album=url)

        return True

class PlsParser(PlaylistParser):
    PLAYLIST_EXTS.append('.pls')
    REGEX = re.compile(r'[fF]ile(\d+)=(.*?)\n[tT]itle(\1)=(.*?)\n', re.DOTALL)

    def _do_parse_file(self, file):
        data = file.read()
        items = self.REGEX.findall(data)

        if items:
            basedir = os.path.dirname(file.url)
            for item in items:
                url = self._get_url_from_path(basedir, item[1])
                self.add_url(url, title=url, album=item[3])

        return True
   
class ASXParser(PlaylistParser):
    PLAYLIST_EXTS.append('.asx')
    REGEX = re.compile(r'''<ref\s+href\s*=\s*(['"])(.*?)\1''',
        re.DOTALL | re.IGNORECASE | re.MULTILINE)

    def _do_parse_file(self, file):
        data = file.read()
        items = self.REGEX.findall(data)

        if items:
            basedir = os.path.dirname(file.url)
            for item in items:
                url = self._get_url_from_path(basedir, item[1])
                self.add_url(url)

        return True
