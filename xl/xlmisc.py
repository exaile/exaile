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

import time
import trackslist, tracks, covers, md5, threading, re
import sys, httplib, urlparse, os, os.path, urllib, media
import common, traceback, gc, xl.db, gobject


import cStringIO
from gettext import gettext as _
import prefs

opener = urllib.FancyURLopener()
opener.addheaders.pop(0)
opener.addheader("User-Agent","Mozilla")

import pygtk
pygtk.require('2.0')
import gtk, gobject, pango

from gtk.gdk import SCROLL_LEFT, SCROLL_RIGHT, SCROLL_UP, SCROLL_DOWN

try:
    import gtkhtml2
    GNOME_EXTRAS_AVAIL = True
except ImportError:
    GNOME_EXTRAS_AVAIL = False
try:
    import egg.trayicon
    USE_TRAY = 'egg'
except ImportError:
    if hasattr(gtk, 'StatusIcon'):
        USE_TRAY = 'gtk'
    else:
        USE_TRAY = None

try:
    import sexy
    SEXY_AVAIL = True
except ImportError:
    SEXY_AVAIL = False

"""
    This file contains every miscellanious dialog and class that is not over
    300 lines of code.  Once they read 300+ lines, they should be put into
    their own file
"""

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
    
    return gtk.gdk.pixbuf_new_from_file('images%sdefault_theme%s%s.png' 
        % (os.sep, os.sep, id))

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
        self.playpause.connect('activate', self.exaile.toggle_pause)
        self.menu.append_item(self.playpause)

        self.menu.append(_("Next"), self.exaile.on_next, 'gtk-media-next')
        self.menu.append(_("Previous"), self.exaile.on_previous,
            'gtk-media-previous')
        self.menu.append_separator()
        self.menu.append(_("Preferences"), 
            lambda e, a: prefs.Preferences(self.exaile).run(),
            'gtk-preferences')
        self.menu.append(_("Plugins"), self.exaile.show_plugin_manager,
            'gtk-execute')
        self.menu.append_separator()
        self.menu.append(_("Quit"), self.exaile.on_quit, 'gtk-quit')

    def update_menu(self):
        track = self.exaile.current_track
        if not track or not track.is_playing():
            self.image.set_from_stock('gtk-media-play',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Play"))
        elif track.is_playing():
            self.image.set_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Pause"))

    def toggle_exaile_visibility(self):
        if self.emit('toggle-hide'): return
        if not self.exaile.window.get_property('visible'):
            self.exaile.window.show_all()
            self.exaile.setup_location()
        else:
            self.exaile.window.hide()

    def set_tooltip(self, tip): # to be overridden
        """
            Sets the tooltip for the tray icon
        """
        pass

    def destroy(self): # to be overridden
        pass

class EggTrayIcon(BaseTrayIcon):
    def __init__(self, exaile):
        BaseTrayIcon.__init__(self, exaile)

        self.tips = gtk.Tooltips()
        self.icon = egg.trayicon.TrayIcon('Exaile!')
        self.box = gtk.EventBox()
        self.icon.add(self.box)

        image = gtk.Image()
        image.set_from_file('images%strayicon.png' % os.sep)
        self.box.add(image)
        self.box.connect('button_press_event',
            self.button_pressed)
        self.box.connect('scroll-event',
            self.scroll)
        self.box.connect('enter-notify-event', lambda *e: 
            self.exaile.show_osd(tray=True))
        self.icon.show_all()

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
            v = self.exaile.volume.get_value()
            if ev.direction in [SCROLL_RIGHT, SCROLL_UP]:
                v += 5
            else:
                v -= 5

            if v < 0: v = 0
            elif v > 120: v = 120

            self.exaile.volume.set_value(v)
            self.exaile.on_volume_set(self.exaile.volume, None, v)

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
        self.icon.destroy()

class GtkTrayIcon(BaseTrayIcon):
    def __init__(self, exaile):
        BaseTrayIcon.__init__(self, exaile)
        self.icon = icon = gtk.StatusIcon()
        icon.set_tooltip('Exaile!')
        icon.set_from_file('images%strayicon.png' % os.sep)
        icon.connect('activate', self.activated)
        icon.connect('popup-menu', self.popup)

    def activated(self, icon):
        self.toggle_exaile_visibility()

    def popup(self, icon, button, time):
        self.update_menu()
        self.menu.popup(None, None, gtk.status_icon_position_menu,
            button, time, self.icon)

    def set_tooltip(self, tip):
        self.icon.set_tooltip(tip)

    def destroy(self):
        self.icon.set_visible(False)

if USE_TRAY == 'egg':
    TrayIcon = EggTrayIcon
elif USE_TRAY == 'gtk':
    TrayIcon = GtkTrayIcon
else:
    TrayIcon = None

FETCHER = None
def get_cover_fetcher(exaile):
    """
        gets the cover fetcher instance
    """
    global FETCHER

    if not CoverFetcher.stopped:
        return FETCHER

    FETCHER = CoverFetcher(exaile)
    return FETCHER

class CoverWrapper(object):
    """
        Wraps a cover object
    """
    def __init__(self, artist, album, location):
        self.artist = artist
        self.album = album
        self.location = location

    def __str__(self):
        title = "%s - %s" % (self.artist, self.album)
        if len(title) > 12:
            title = title[0:10] + "..."
        return title

class CoverFetcher(object):
    """
        Fetches all covers in the library
    """
    stopped = True

    def __init__(self, parent):
        """ 
            Initializes the dialog
        """
        self.exaile = parent
        self.db = self.exaile.db
        xml = gtk.glade.XML('exaile.glade', 'CoverFetcher', 'exaile')
        self.icons = xml.get_widget('cover_icon_view')

        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_model(self.model)
        self.icons.set_item_width(90)
        self.artists = None
        self.go = False
        self.icons.set_text_column(0)
        self.icons.set_pixbuf_column(1)
        self.icons.connect('item-activated',
            self.item_activated)
        self.status = xml.get_widget('cover_status_bar')
        self.icons.connect('motion-notify-event',
            self.mouse_move)
        self.icons.connect('leave-notify-event',
            lambda *e: self.status.set_label(''))
        self.dialog = xml.get_widget('CoverFetcher')
        self.progress = xml.get_widget('fetcher_progress')
        self.label = xml.get_widget('fetcher_label')

        xml.get_widget('fetcher_cancel_button').connect('clicked',
            self.cancel)
        self.stopstart = xml.get_widget('fetcher_stop_button')
        self.stopstart.connect('clicked', self.toggle_running)

        self.current = 0
        self.dialog.show_all()
        finish()
        self.total = self.calculate_total()
        self.label.set_label("%s covers left to collect." % self.total)
        if self.go:
            self.toggle_running(None)

    def cancel(self, event):
        """
            Closes the dialog
        """
        CoverFetcher.stopped = True
        self.dialog.hide()

    def toggle_running(self, event):
        """
            Toggles the running state of the fetcher
        """
        if CoverFetcher.stopped:
            if not self.artists:
                self.go = True
                self.stopstart.set_label("Stop")
                return
                
            CoverFetcher.stopped = False
            self.stopstart.set_label("Stop")
            self.fetch_next()
        else:
            self.stopstart.set_label("Start")
            CoverFetcher.stopped = True
            if self.cover_thread:
                self.cover_thread.abort()

    def fetch_next(self, event=None):
        """
            Fetches the next cover in line
        """
        if not self.artists:
            self.label.set_label("All Covers have been Fetched.")
            self.stopstart.set_sensitive(False)
            return
        self.artist = self.artists[0]
        if CoverFetcher.stopped: return
        
        try:
            self.album = self.needs[self.artist].pop()
        except IndexError:
            del self.needs[self.artist]
            self.artists.remove(self.artist)
            self.fetch_next()
            return

        if not self.needs[self.artist]:
            del self.needs[self.artist]
            self.artists.remove(self.artist)

        locale = self.exaile.settings.get('amazon_locale', 'us')
        self.cover_thread = covers.CoverFetcherThread("%s - %s" %
            (self.artist, self.album),
            self.got_covers, locale=locale)
        self.cover_thread.start()
        self.label.set_label("%s left: %s by %s" % 
            ((self.total - self.current), self.album, self.artist))

    def got_covers(self, covers):
        """
            Called when the fetcher thread has gotten all the covers for this
            album
        """
        if self.stopped: return
        artist_id = tracks.get_column_id(self.db, 'artists', 'name', self.artist)
        album_id = tracks.get_album_id(self.db, artist_id, self.album)
        if len(covers) == 0:
            self.db.execute("UPDATE albums SET image=? WHERE id=?",
                ('nocover', album_id,))
            
        # loop through all of the covers that have been found
        for cover in covers:
            if(cover['status'] == 200):
                cover.save("%s%scovers" % (self.exaile.get_settings_dir(),
                    os.sep))
                log(cover['filename'])

                try:
                    self.db.execute("UPDATE albums SET image=? WHERE id=?", 
                        (cover['md5'] + ".jpg", album_id))
                except:
                    log_exception()

                image = "%s%scovers%s%s" % (self.exaile.get_settings_dir(),
                    os.sep, os.sep, cover['md5'] + ".jpg")
                loc = image
                image = gtk.gdk.pixbuf_new_from_file(image)
                image = image.scale_simple(80, 80, 
                    gtk.gdk.INTERP_BILINEAR)
                
                if self.found.has_key("%s - %s" % (self.artist.lower(), self.album.lower())):
                    iter = self.found["%s - %s" % (self.artist.lower(), self.album.lower())] 
                    object = self.model.get_value(iter, 2)
                    object.location = loc
                    self.model.set_value(iter, 1, image)
                break

        if self.stopped: return
        self.current = self.current + 1
        self.progress.set_fraction(float(self.current) / float(self.total))
        self.fetch_next()

    def mouse_move(self, widget, event):
        """
            Called when the mouse moves in the icon view
        """
        x, y = event.get_coords()
        x = int(x)
        y = int(y)

        path = self.icons.get_path_at_pos(x, y)
        if not path: 
            self.status.set_label('')
            return

        iter = self.model.get_iter(path)
        object = self.model.get_value(iter, 2)

        self.status.set_markup("<b>%s by %s</b>" % (object.album,
            object.artist))

    def item_activated(self, iconview, path):
        """
            Called when an icon is double clicked
        """
        iter = self.model.get_iter(path)
        object = self.model.get_value(iter, 2)
        CoverWindow(self.dialog, object.location, "%s by %s" % (object.album,
            object.artist))

    def calculate_total(self):
        """
            Finds the albums that need a cover
        """
        all = self.db.select("SELECT artists.name, albums.name, albums.image "
            "FROM tracks,albums,artists WHERE blacklisted=0 AND type=0 AND ( "
            "artists.id=tracks.artist AND albums.id=tracks.album) "
            " ORDER BY artists.name, albums.name")
        self.needs = dict()

        self.found = dict()
        count = 0
        for (artist, album, image) in all:
            if not self.needs.has_key(artist):
                self.needs[artist] = []
            if album in self.needs[artist]: continue

            if not image:
                self.needs[artist].append(album)
                image = "images%snocover.png" % os.sep
            elif image.find("nocover") > -1:
                continue
            elif image.find("nocover") == -1: 
                image = "%s%scovers%s%s" % (self.exaile.get_settings_dir(),
                    os.sep, os.sep, image)

            if self.found.has_key("%s - %s" % (artist.lower(), album.lower())):
                continue

            title = CoverWrapper(artist, album, image)
            image = gtk.gdk.pixbuf_new_from_file(image)
            image = image.scale_simple(80, 80, 
                gtk.gdk.INTERP_BILINEAR)

            self.found["%s - %s" % (artist.lower(), album.lower())] = \
                self.model.append([title, image, title])
            if count >= 30: 
                count = 0
                t = 0
                for k, v in self.needs.iteritems():
                    t += len(v)
                self.label.set_label("%s covers left to collect." % t)
                finish()
            count += 1

        count = 0
        for k, v in self.needs.iteritems():
            count += len(v)

        self.artists = self.needs.keys()
        self.artists.sort()

        return count

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
        hbox.pack_start(btn, False, False)
        
        self.show_all()

    def rename(self, widget, event):
        """
            Renames the tab
        """
        dialog = TextEntryDialog(self.exaile.window, 
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
    message = traceback.format_exc()
    gobject.idle_add(__log_exception, message)

def __log_exception(message):
    """
        Logs an exception
    """
    message = message.split("\n")
    for line in message:
        log(line)

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
        gobject.idle_add(self.done_func, "%s%s" % (self.server, self.path), text)

class BrowserWindow(gtk.VBox):
    """
        An html window for wikipedia information
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

            self.entry = gtk.Entry()
            self.entry.connect('activate', self.entry_activate)
            top.pack_start(self.entry, True, True)
            self.pack_start(top, False, True)

        self.view = gtkhtml2.View()
        self.doc = gtkhtml2.Document()
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.doc.open_stream('text/html')
        self.doc.write_stream('<html><body><b>Loading requested'
            ' information...</b></body></html>')
        self.doc.close_stream()
        scroll.add(self.view)
        self.view.set_document(self.doc)

        self.pack_start(scroll, True, True)

        self.cache_dir = '%s%scache' % (exaile.get_settings_dir(), os.sep)
        self.exaile = exaile

        self.server = ''
        self.history = [url]
        self.current = 0

        if url:
            self.load_url(url, self.action_count, False)
            if not self.nostyles:
                self.entry.set_sensitive(False)

    def set_text(self, text):
        """
            Sets the html for this page
        """
        self.doc.open_stream('text/html')
        self.doc.write_stream('<html><body><b>%s</b></body></html' % text)
        self.doc.close_stream()

    def entry_activate(self, *e):
        """
            Called when the user presses enter in the address bar
        """
        url = self.entry.get_text()
        self.link_clicked(self.doc, url)

    def request_url(self, document, url, stream, try_base_uri=True):
        """
            Called when the document requests an outside url (images/etc)
        """
        h = opener.open(url)
        stream.write(h.read())
        h.close()

    def on_next(self, widget):
        """
            Goes to the next entry in history
        """
        self.current += 1 
        self.link_clicked(self.doc, self.history[self.current], False)
        if self.current >= len(self.history) - 1:
            self.next.set_sensitive(False)
        if len(self.history):
            self.back.set_sensitive(True)
            
    def on_back(self, widget):
        """
            Previous entry
        """
        self.current -= 1
        self.link_clicked(self.doc, self.history[self.current], False)
        if self.current == 0:
            self.back.set_sensitive(False)
        if len(self.history):
            self.next.set_sensitive(True)

    @common.threaded
    def load_url(self, url, action_count, history=False):
        """
            Loads a URL, either from the cache, or from the website specified
        """

        if history:
            self.history = self.history[:self.current + 1]
            self.history.append(url)
            self.current = len(self.history) - 1
        info = urlparse.urlparse(url)
        self.protocol = info[0]
        self.server = info[1]
        self.path = info[2]
        cache_file = "%s/browser_%s.html" % (self.cache_dir, md5.new(url).hexdigest())
        if os.path.isfile(cache_file):
            h = open(cache_file, 'r')
            data = h.read()
            h.close()
            self.page_loaded(url, data, False)
            return

        f = opener.open(url)
        data = f.read()
        f.close()

        if self.action_count != action_count: return
        self.page_loaded(url, data, True)

        if not self.nostyles:
            if self.history and history:
                self.back.set_sensitive(True)
                self.next.set_sensitive(False)

    def replace(self, match):
        """
            Finds out if it is a relative path and modifies it accordingly.
            Called by the re.sub in PageLoaded
        """
        link = match.group(3)
        if link.find("://") == -1:
            char = ""
            if not link.startswith("/"): char = "/"
            link = "%s://%s%s%s" % (self.protocol, self.server, char, link)
        return "%s=%s%s%s" % (match.group(1), match.group(2), link,
            match.group(2))

    def sanitize(self, text):
        """
            Removes styles, images, and etc
        """
        rel = re.compile('<(style|img|script)[^<]*[^>]*>',
            re.DOTALL|re.IGNORECASE)
        text = rel.sub('', text)

        # this one might be temporary.  It's to clean out some php errors that
        # lyrc.com.ar probably doesn't know about because their background is
        # black and this warning is also black
        rel = re.compile('<noscript>.*?</noscript>',
            re.DOTALL|re.IGNORECASE)
        text = rel.sub('', text)
        rel = re.compile('<table.*?</table>',
            re.DOTALL|re.IGNORECASE)
        text = rel.sub('<hr><br><br>', text)
        # end possible temporary solution

        rel = re.compile('<\/?font[^>]*>', re.DOTALL|re.IGNORECASE)
        text = rel.sub('', text)
        text = re.sub('bgcolor="[^"]*"', '', text)
        text = text.replace('BADSONG', '')
        text = text.replace('If none is your song', '')
        text = text.replace('Correct :', '')
        text = text.replace('Add a lyric', '')
        text = text.replace('Did you find an error on this lyric? Report It.',
            '')
        return text

    def page_loaded(self, url, data, save=True):
        """
            Loads a page into the html window, and optionally saves it to the
            cache
        """
        if not self.nostyles: gobject.idle_add(self.entry.set_text, url)
        if url.find("http://") == -1: url = "%s://%s" % (self.protocol, url)
        self.url = url
        cache_file = "%s/browser_%s.html" % (self.cache_dir, 
            md5.new(url).hexdigest())
        if save:
            rel = re.compile("(href|src)=(['\"])([^'\"]*)(['\"])", 
                re.DOTALL|re.IGNORECASE)
            data = rel.sub(self.replace, data)
            data = re.sub('(id|style|class)="([^"]*)"', '', data)
            data = re.sub('<input .*?>', '', data) # nix pesky form fields
            if self.nostyles:
                data = self.sanitize(data)
            h = open(cache_file, 'w')
            h.write(data)
            h.close()
        else:
            h = open(cache_file, 'r')
            data = h.read()
            h.close()

        self.doc = gtkhtml2.Document()
        self.doc.connect('request_url', self.request_url)
        self.doc.connect('link_clicked', self.link_clicked)
        self.doc.open_stream('text/html')
        self.doc.write_stream(data)
        self.doc.close_stream()

        gobject.idle_add(self.view.set_document, self.doc)
        gobject.idle_add(self.view.queue_draw)

        if not self.nostyles:
            gobject.idle_add(self.entry.set_sensitive, True)

    def link_clicked(self, document, link, history=True):
        """
            Link clicked
        """
        self.doc = gtkhtml2.Document()
        self.doc.open_stream('text/html')
        self.doc.write_stream('<html><body><b>Loading requested'
            ' information...</b></body></html>')
        self.doc.close_stream()
        self.view.set_document(self.doc)
        self.action_count += 1
        self.load_url(link, self.action_count, history)
        if not self.nostyles:
            self.entry.set_sensitive(False)

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
        logo = gtk.gdk.pixbuf_new_from_file('images%sexailelogo.png' % os.sep)
        self.dialog.set_logo(logo)
        self.dialog.set_version(str(version))
        self.dialog.set_transient_for(parent)
        self.dialog.run()
        self.dialog.destroy()

class CoverWindow(object):
    """
        Shows the fullsize cover in a window
    """
    def __init__(self, parent, cover, title=''):
        """
            Initializes and shows the cover
        """
        xml = gtk.glade.XML('exaile.glade', 'CoverWindow', 'exaile')
        window = xml.get_widget('CoverWindow')
        box = xml.get_widget('cw_box')
        pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
        image = gtk.Image()
        image.set_from_file(cover)
        image.set_size_request(pixbuf.get_width(), pixbuf.get_height())
        eventbox = gtk.EventBox()
        eventbox.add(image)
        box.pack_start(eventbox)

        eventbox.connect('button_release_event', self.button_press)
        window.set_title(title)
        window.set_transient_for(parent)
        window.show_all()
        self.window = window

    def button_press(self, widget, event):
        """
            Called when someone clicks on the event box
        """
        self.window.destroy()

class TextEntryDialog(object):
    """
        Shows a dialog with a single line of text
    """
    def __init__(self, parent, message, title):
        """
            Initializes the dialog
        """
        self.parent = parent
        xml = gtk.glade.XML('exaile.glade', 'TextEntryDialog', 'exaile')
        self.dialog = xml.get_widget('TextEntryDialog')
        xml.get_widget('ted_question_label').set_label(message)
        self.dialog.set_title(title)
        self.dialog.set_transient_for(parent)

        xml.get_widget('ted_cancel_button').connect('clicked',
            lambda e: self.dialog.response(gtk.RESPONSE_CANCEL))

        self.entry = xml.get_widget('ted_entry')
        xml.get_widget('ted_ok_button').connect('clicked',
            lambda e: self.dialog.response(gtk.RESPONSE_OK))
        self.entry.connect('activate', 
            lambda e: self.dialog.response(gtk.RESPONSE_OK))

    def run(self):
        """
            Runs the dialog, waiting for input
        """
        return self.dialog.run()

    def response(self):
        """
            Shows the dialog and returns the result
        """
        return self.response_code

    def get_value(self):
        """
            Returns tthe text value
        """
        return self.entry.get_text()

    def set_value(self, value):
        """
            Sets the value of the text
        """
        self.entry.set_text(value)

    def destroy(self):
        """
            Destroys the dialog
        """
        self.dialog.destroy()

class CoverFrame(object):
    """
        Fetches all album covers for a string, and allows the user to choose
        one out of the list
    """
    def __init__(self, parent, track, search=False):
        """
            Expects the parent control, a track, an an optional search string
        """
        self.xml = gtk.glade.XML('exaile.glade', 'CoverFrame', 'exaile')
        self.window = self.xml.get_widget('CoverFrame')
        self.window.set_title("%s - %s" % (track.artist, track.album))
        self.window.set_transient_for(parent.window)

        self.exaile = parent
        self.track = track
        self.db = parent.db
        self.prev = self.xml.get_widget('cover_back_button')
        self.prev.connect('clicked', self.go_prev)
        self.prev.set_sensitive(False)
        self.next = self.xml.get_widget('cover_forward_button')
        self.next.connect('clicked', self.go_next)
        self.xml.get_widget('cover_newsearch_button').connect('clicked',
            self.new_search)
        self.xml.get_widget('cover_cancel_button').connect('clicked',
            lambda *e: self.window.destroy())
        self.ok = self.xml.get_widget('cover_ok_button')
        self.ok.connect('clicked',
            self.on_ok)
        self.box = self.xml.get_widget('cover_image_box')
        self.cover = ImageWidget()
        self.cover.set_image_size(350, 350)
        self.box.pack_start(self.cover, True, True)

        self.last_search = "%s - %s" % (track.artist, track.album)

        if not search:
            locale = self.exaile.settings.get('amazon_locale', 'us')
            covers.CoverFetcherThread("%s - %s" % (track.artist, track.album),
                self.covers_fetched, locale=locale).start()
        else:
            self.new_search()

    def new_search(self, widget=None):
        """
            Creates a new search string
        """
        dialog = TextEntryDialog(self.exaile.window,
            _("Enter the search text"), _("Enter the search text"))
        dialog.set_value(self.last_search)
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_OK:
            self.last_search = dialog.get_value()
            self.exaile.status.set_first(
                _("Searching for ") + self.last_search + "...")
            self.window.hide()

            locale = self.exaile.settings.get('amazon_locale', 'us')
            covers.CoverFetcherThread(self.last_search,
                self.covers_fetched, True, locale=locale).start()

    def on_ok(self, widget=None):
        """
            Chooses the current cover and saves it to the database
        """
        track = self.track
        cover = self.covers[self.current]
        artist_id = tracks.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        self.db.execute("UPDATE albums SET image=? WHERE id=?", (cover.filename(),
            album_id))

        if track == self.exaile.player.current:
            self.exaile.stop_cover_thread()
            self.exaile.cover.set_image("%s%scovers%s%s" %
                (self.exaile.get_settings_dir(), os.sep, os.sep,
                cover.filename()))
        self.window.destroy()

    def go_next(self, widget):
        """
            Shows the next cover
        """
        if self.current + 1 >= len(self.covers): return
        self.current = self.current + 1
        self.show_cover(self.covers[self.current])
        if self.current + 1 >= len(self.covers):
            self.next.set_sensitive(False)
        if self.current - 1 >= 0:
            self.prev.set_sensitive(True)

    def go_prev(self, widget):
        """
            Shows the previous cover
        """
        if self.current - 1 < 0: return
        self.current = self.current - 1
        self.show_cover(self.covers[self.current])

        if self.current + 1 < len(self.covers):
            self.next.set_sensitive(True)
        if self.current - 1 < 0:
            self.prev.set_sensitive(False)

    def show_cover(self, c):
        """
            Shows the current cover
        """
        c.save("%s%scovers%s" % (self.exaile.get_settings_dir(),
            os.sep, os.sep))

        log(c.filename())

        self.cover.set_image("%s%scovers%s%s" % (self.exaile.get_settings_dir(),
            os.sep, os.sep, c.filename()))

        self.window.show_all()

    def covers_fetched(self, covers):
        """
            Called when the cover fetcher thread has fetched all covers
        """
        self.exaile.status.set_first(None)

        if len(covers) <= 0:
            common.error(self.exaile.window, _("Sorry, no covers were found."))
            self.covers = []
            self.next.set_sensitive(False)
            self.ok.set_sensitive(False)
            self.window.show_all()
            return

        if len(covers) > 1: self.next.set_sensitive(True)
        else: self.next.set_sensitive(False)
        self.ok.set_sensitive(True)

        self.covers = covers
        self.current = 0

        self.show_cover(self.covers[self.current])

class LibraryManager(object):
    """
        Allows you to choose which directories are in your library
    """
    def __init__(self, exaile):
        """
            Initializes the dialog
        """
        self.exaile = exaile
        self.xml = gtk.glade.XML('exaile.glade', 'LibraryManager')
        self.dialog = self.xml.get_widget('LibraryManager')
        self.list = ListBox(self.xml.get_widget('lm_list_box'))
        self.dialog.set_transient_for(exaile.window)
        self.xml.get_widget('lm_add_button').connect('clicked',
            self.on_add)
        self.xml.get_widget('lm_remove_button').connect('clicked',
            self.on_remove)

        self.xml.get_widget('lm_cancel_button').connect('clicked',
            lambda e: self.dialog.response(gtk.RESPONSE_CANCEL))
        self.xml.get_widget('lm_apply_button').connect('clicked',
            self.on_apply)

        items = exaile.settings.get("search_paths", "").split(":")
        self.items = []
        for i in items:
            if i: self.items.append(i)

        if self.items:
            self.list.set_rows(self.items)

    def run(self):
        """
            Runs the dialog, waiting for a response before any other gui
            events occur
        """
        return self.dialog.run()

    def get_response(self):
        """
            Gets the response id
        """
        return self.dialog.get_response()

    def destroy(self):
        """
            Destroys the dialog
        """
        self.dialog.destroy()

    def get_items(self):
        """
            Returns the items in the dialog
        """
        return self.items

    def on_apply(self, widget):
        """
            Saves the paths in the dialog, and updates the library
        """
        self.exaile.settings['search_paths'] = ":".join(self.list.rows)
        self.dialog.response(gtk.RESPONSE_APPLY)

    def on_remove(self, widget):
        """
            removes a path from the list
        """
        item = self.list.get_selection()
        index = self.list.rows.index(item)
        self.list.remove(item)
        selection = self.list.list.get_selection()
        if index >= len(self.list.rows):
            selection.select_path(index - 1)
        else:
            selection.select_path(index)

    def on_add(self, widget):
        """
            Adds a path to the list
        """
        dialog = gtk.FileChooserDialog(_("Add a directory"),
            self.exaile.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (_("Cancel"), gtk.RESPONSE_CANCEL, _("Choose"), gtk.RESPONSE_OK))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.list.append(dialog.get_filename())
        dialog.destroy()

class MultiTextEntryDialog(object):
    """
        Exactly like a TextEntryDialog, except it can contain multiple
        labels/fields.

        Instead of using GetValue, use GetValues.  It will return a list with
        the contents of the fields. Each field must be filled out or the dialog
        will not close.
    """
    def __init__(self, parent, title):
        xml = gtk.glade.XML('exaile.glade', 'MultiTextEntryDialog', 'exaile')

        self.dialog = xml.get_widget('MultiTextEntryDialog')
        self.dialog.set_transient_for(parent)

        self.hbox = xml.get_widget('mte_box')
        self.left = xml.get_widget('mte_left')
        self.right = xml.get_widget('mte_right')
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
        entry.set_width_chars(30)
        self.right.pack_start(entry, True, True)
        label.show()
        entry.show()

        self.fields.append(entry)
    
    def run(self):
        """
            Runs the dialog
        """
        return self.dialog.run()

    def destroy(self):
        """
            Destroys the dialog
        """
        self.dialog.destroy()

    def get_values(self):
        """
            Returns a list of the values from the added fields
        """
        return [a.get_text() for a in self.fields]

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
def get_text_icon(widget, text, width, height):
    """
        Gets a bitmap icon with the specified text, width, and height
    """
    if BITMAP_CACHE.has_key("%s - %sx%s" % (text, width, height)):
        return BITMAP_CACHE["%s - %sx%s" % (text, width, height)]
        
    pixmap = gtk.gdk.Pixmap(None, width, height, 24)
    colormap = gtk.gdk.colormap_get_system()
    white = colormap.alloc_color(65535, 65535, 65535)
    black = colormap.alloc_color(0, 0, 0)
    pixmap.set_colormap(colormap)
    gc = pixmap.new_gc(foreground=black, background=white)

    gc.set_foreground(black)
    pixmap.draw_rectangle(gc, True, 0, 0, width, height)
    fg = colormap.alloc_color(gtk.gdk.color_parse('#456eac'))
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

    BITMAP_CACHE["%s - %sx%s" % (text, width, height)] = pixbuf
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

        color = gtk.gdk.color_parse(settings['osd_bgcolor'])
        self.settings = settings
        self.event = self.xml.get_widget('popup_event_box')
        self.box = self.xml.get_widget('image_box')
        self.window.modify_bg(gtk.STATE_NORMAL, color)
        self.title = self.xml.get_widget('popup_title_label')

        self.window.set_size_request(settings['osd_w'], settings['osd_h'])
        self.cover = ImageWidget()
        self.box.pack_start(self.cover, False, False)
        self.window.move(settings['osd_x'], settings['osd_y'])
        self.cover.set_image_size(settings['osd_h'] - 8, settings['osd_h'] - 8)
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

        settings['osd_x'] = x
        settings['osd_y'] = y
        settings['osd_h'] = h
        settings['osd_w'] = w
    
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
        for item in ('title', 'artist', 'album', 'length', 'track', 'bitrate',
            'genre', 'year', 'rating'):
            try:
                value = getattr(track, item)
                if type(value) != str and type(value) != unicode:
                    value = unicode(value)
                text = text.replace("{%s}" % item, value)
            except AttributeError:
                pass

        text = text.replace("{volume}", "%d%%" %
            self.exaile.get_volume_percent())
        text = text.replace("\\{", "{")
        text = text.replace("\\}", "}")
        text = text.replace("&", "&amp;")
        self.show_osd(text, cover)

    def show_osd(self, title, cover):
        """
            Displays the popup for 4 seconds
        """
        if self.__timeout:
            gobject.source_remove(self.__timeout)
            self.window.hide()
        
        text = "<span font_desc='%s' foreground='%s'>%s</span>" % \
            (self.settings['osd_text_font'], self.settings['osd_textcolor'],
            title)
        self.title.set_markup(text)

        if cover == None:
            cover = 'images%snocover.png' % os.sep

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
    info['osd_bgcolor'] = settings.get("osd_bgcolor", "#567ea2")
    info['osd_w'] = settings.get_int("osd_w", 400)
    info['osd_h'] = settings.get_int("osd_h", 95)
    info['osd_y'] = settings.get_int("osd_y", 0)
    info['osd_x'] = settings.get_int("osd_x", 0)
    info['osd_display_text'] = settings.get('osd_display_text', 
        prefs.TEXT_VIEW_DEFAULT)
    info['osd_text_font'] = settings.get('osd_text_font',
        'Sans 10')
    info['osd_textcolor'] = settings.get('osd_textcolor',
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

class PlaylistParser(object):
    def __init__(self,name):

        self.name = name
        self.url = []

    def add_url(self,url):
        try: 
            url = list(urlparse.urlsplit(url))
        except:
            pass

        if not url[0]:
            url[0] = 'file'
        self.url.append(url)

    def get_urls(self):
        return self.url

    def get_full(self):
        return [urlparse.urlunsplit(u) for u in self.url]


    def get_name(self):
        return self.name

    def parse_file(self,filename):
        raise NotImplementedError

class M3UParser(PlaylistParser):
    
    def __init__(self,name,filename = None):
        super(M3UParser,self).__init__(name)
        if filename:
            self.parse_file(filename)

    def parse_file(self,filename):

        file = urllib.urlopen(filename)

        for line in file.readlines():
            line = line.strip()
            if line[0] == "#" or line == '' : continue
            if urlparse.urlsplit(line)[0]:
                url = line
            else:
                if not os.path.isabs(line): # m3u entries can be relative paths
                    url = os.path.dirname(filename) + os.path.sep + line
                else:
                    url = line
            self.add_url(url)
        return True

class PlsParser(PlaylistParser):
    def __init__(self,name,filename = None):
        super(PlsParser,self).__init__(name)
        if filename:
            self.parse_file(filename)

    def parse_file(self,filename):

        (path,file) = os.path.split(filename)
        file = urllib.urlopen(filename)

        rgx = re.compile('[Ff]ile ?\d+ ?=(.+)')
        for line in file.readlines():
            line = line.strip() 
            if rgx.match(line):
                rg = rgx.match(line).group(1).strip()
                if urlparse.urlsplit(rg)[0]:
                    url = rg
                else:
                    if not os.path.isabs(rg): # m3u entries can be relative paths
                        url = os.path.dirname(filename) + os.path.sep + rg
                    else:
                        url = rg
                self.add_url(url)
        return True
   


