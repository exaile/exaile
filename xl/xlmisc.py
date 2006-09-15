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
import common, traceback, gc
from pysqlite2.dbapi2 import OperationalError
import cStringIO
from gettext import gettext as _

opener = urllib.FancyURLopener()
opener.addheaders.pop(0)
opener.addheader("User-Agent","Mozilla")

import pygtk
pygtk.require('2.0')
import gtk, gobject, pango

try:
    import gtkhtml2
    GNOME_EXTRAS_AVAIL = True
except ImportError:
    GNOME_EXTRAS_AVAIL = False

try:
    import egg.trayicon
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

"""
    This file contains every miscellanious dialog and class that is not over
    300 lines of code.  Once they read 300+ lines, they should be put into
    their own file
"""

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
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            hbox.pack_start(image, False, True)
            label = gtk.Label(label)
            label.set_alignment(0, 0)
            hbox.pack_start(label, True, True)
        else:
            item = gtk.MenuItem(label)
            self.label = item.get_child()

        item.connect('activate', callback, data)
        gtk.Menu.append(self, item)
        item.show_all()
        return item

    def append_item(self, item):
        """
            Appends a menu item
        """
        gtk.Menu.append(self, item)
        item.show_all()

    def append_menu(self, label, menu):
        """
            Appends a submenu
        """

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
        return theme.load_icon(id, size, gtk.ICON_LOOKUP_NO_SVG)
    except gobject.GError:
       return gtk.gdk.pixbuf_new_from_file('images%sdefault_theme%s%s.png' 
        % (os.sep, os.sep, id))

class ThreadRunner(threading.Thread):
    """
        Runs operations in a thread
    """
    def __init__(self, run_func, end_func=None, *funcparams):
        """
            Expects a start function and an end function
        """
        threading.Thread.__init__(self)
        self.params = funcparams
        self.run_func = run_func
        self.end_func = end_func
        self.stopped = False
        self.lock = None

    def run(self):
        """
            Runs the thread
        """
        if self.lock: self.lock.acquire()
        if self.stopped: return
        self.run_func(self)
        if self.end_func: self.end_func(self)
        if self.lock: 
            self.lock.release()
            print 'released lock'

# this class is taken from Quodlibet's code, which is in turn based on
# rhythmbox's code
# thanks Joe Wreschnig, Mihcael Urman
class VolumeControl(gtk.EventBox):
    """
        A volume control slider
    """
    _req = (26, 170)
    UP = [gtk.gdk.SCROLL_UP, gtk.gdk.SCROLL_LEFT]

    def __init__(self, child, func):
        """
            Initializes the widget
        """
        gtk.EventBox.__init__(self)
        button = gtk.Button()
        button.set_size_request(32, 32)
        if child: button.add(child)
        self.add(button)
        self.func = func
        button.connect('clicked', self.__clicked)
        self.show_all()

        window = self.__window = gtk.Window(gtk.WINDOW_POPUP)

        frame = gtk.Frame()
        frame.set_border_width(0)
        frame.set_shadow_type(gtk.SHADOW_OUT)

        hscale = gtk.VScale(gtk.Adjustment(0, 0, 120))
        hscale.set_size_request(*(self._req))
        window.connect('button-press-event', self.__button)
        hscale.connect('key-press-event', self.__key)
        hscale.set_draw_value(False)
        hscale.set_update_policy(gtk.UPDATE_CONTINUOUS)
        self.scale = hscale
        window.add(frame)
        frame.add(hscale)
        self.connect('scroll-event', self.scroll, hscale)
        self.__window.connect('scroll-event', self.__window_scroll)
        self.scale.connect_object('scroll-event', self.emit, 'scroll-event')
        self.scale.connect('change-value', lambda *e: func())
        self.scale.set_inverted(True)
        self.slider = self.scale

    def __window_scroll(self, window, event):
        """
            Called when a scroll event occurs
        """
        self.emit('scroll-event', event)

    def _move_to(self, x, y, w, h, ww, wh, pad=3):
        """
            Moves the control to the correct location'
        """
        return ((x + (w - ww)//2), y + h + pad)

    def get_top_parent(self, widget):
        """
            Returns the top widget
        """
        return widget and widget.get_ancestor(gtk.Window)

    def __clicked(self, button):
        """
            called when the user clicks the volumn button
        """
        if self.__window.get_property('visible'): return
        self.__window.child.show_all()
        self.__window.size_request()
        x, y = self.child.window.get_origin()
        w, h = self.child.window.get_size()        
        ww, wh = self.__window.child.parent.get_size()
        sx, sy = self._move_to(x, y - 208, w, h, ww, wh, pad=3)
        self.__window.set_transient_for(self.get_top_parent(self))
        self.__window.move(sx, sy)
        self.__window.show()
        self.__window.grab_focus()
        self.__window.grab_add()
        pointer = gtk.gdk.pointer_grab(
            self.__window.window, True,
            gtk.gdk.BUTTON_PRESS_MASK |
            gtk.gdk.BUTTON_RELEASE_MASK |
            gtk.gdk.BUTTON_MOTION_MASK |
            gtk.gdk.POINTER_MOTION_MASK |
            gtk.gdk.SCROLL_MASK, None, None, gtk.get_current_event_time())
        keyboard = gtk.gdk.keyboard_grab(
            self.__window.window, True, gtk.get_current_event_time())

        if pointer != gtk.gdk.GRAB_SUCCESS or keyboard != gtk.gdk.GRAB_SUCCESS:
            self.__window.grab_remove()
            self.__window.hide()

            if pointer == gtk.gdk.GRAB_SUCCESS:
                gtk.gdk.pointer_ungrab(gtk.get_current_event_time())
            if keyboard == gtk.gdk.GRAB_SUCCESS:
                gtk.gdk.keyboark_ungrab(gtk.get_current_event_time())

    def scroll(self, widget, ev, hscale=None):
        """
            Called when a scroll event occurs (I'm assuming with the scroll
            wheel on the mouse)
        """
        v = self.slider.get_value()
        if ev.direction in self.UP: v += 8
        else: v -= 8

        if v < 0: v = 0
        elif v > 120: v = 120
        self.slider.set_value(v)
        self.func()

    def __button(self, widget, ev):
        """
            if the mouse gets clicked outside of the slider, hide this control    
        """
        self.__popup_hide()

    def __key(self, hscale, ev):
        """
            Hide the slider if enter, space or escape are pressed
        """
        if ev.string in ["\n", "\r", " ", "\x1b"]: # enter, space, escape
            self.__popup_hide()

    def __popup_hide(self):
        """
            Hides the slider
        """
        self.__window.grab_remove()
        gtk.gdk.pointer_ungrab(gtk.get_current_event_time())
        gtk.gdk.keyboard_ungrab(gtk.get_current_event_time())
        self.__window.hide()

class TrayIcon(object):
    """
        System tray icon
    """
    def __init__(self, exaile):
        """
            Initializes the tray icon
        """
        self.exaile = exaile

        self.tips = gtk.Tooltips()
        self.icon = egg.trayicon.TrayIcon('Exaile!')
        self.box = gtk.EventBox()
        self.icon.add(self.box)

        image = gtk.Image()
        image.set_from_file('images%strayicon.png' % os.sep)
        self.box.add(image)
        self.setup_menu()
        self.box.connect('button_press_event',
            self.button_pressed)
        self.box.connect('scroll-event',
            self.exaile.volume.scroll)
        self.box.connect('enter-notify-event', lambda *e: self.exaile.show_popup())
        self.icon.show_all()

    def button_pressed(self, item, event, data=None):
        """
            Called when someone clicks on the icon
        """
        if event.button == 3:
            track = self.exaile.current_track
            if not track or not track.is_playing():
                self.image.set_from_stock('gtk-media-play',
                    gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.label.set_label(_("Play"))
            elif track.is_playing():
                self.image.set_from_stock('gtk-media-pause',
                    gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.label.set_label(_("Pause"))
            self.menu.popup(None, None, None, event.button, event.time)
        elif event.button == 1: 
            if not self.exaile.window.get_property('visible'):
                self.exaile.window.show_all()
            else:
                self.exaile.window.hide()

    def setup_menu(self):
        """
            Sets up the popup menu for the tray icon
        """
        self.menu = Menu()

        self.image = gtk.Image()
        self.image.set_from_stock('gtk-media-play',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
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
        self.menu.append(_("Quit"), self.exaile.on_quit, 'gtk-quit')

    def set_tooltip(self, tip):
        """
            Sets the tooltip for the tray icon
        """
        self.tips.set_tip(self.icon, tip)

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
            self.__item_activated)
        self.status = xml.get_widget('cover_status_bar')
        self.icons.connect('motion-notify-event',
            self.__mouse_move)
        self.icons.connect('leave-notify-event',
            lambda *e: self.status.set_label(''))
        self.dialog = xml.get_widget('CoverFetcher')
        self.dialog.set_transient_for(parent.window)
        self.progress = xml.get_widget('fetcher_progress')
        self.label = xml.get_widget('fetcher_label')

        xml.get_widget('fetcher_cancel_button').connect('clicked',
            self.__cancel)
        self.stopstart = xml.get_widget('fetcher_stop_button')
        self.stopstart.connect('clicked', self.toggle_running)

        self.current = 0
        self.dialog.show_all()
        finish()
        self.total = self.calculate_total()
        self.label.set_label("%s covers left." % self.total)
        if self.go:
            self.toggle_running(None)

    def __cancel(self, event):
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

        self.cover_thread = covers.CoverFetcherThread("%s - %s" %
            (self.artist, self.album),
            self.__got_covers)
        self.cover_thread.start()
        self.label.set_label("%s left: %s by %s" % 
            ((self.total - self.current), self.album, self.artist))

    def __got_covers(self, covers):
        """
            Called when the fetcher thread has gotten all the covers for this
            album
        """
        if self.stopped: return
        if len(covers) == 0:
            self.db.execute("UPDATE albums SET image=? WHERE album=? " \
                "AND artist=?", ('nocover', self.album,
                self.artist))
            
        # loop through all of the covers that have been found
        for cover in covers:
            if(cover['status'] == 200):
                cover.save("%s%scovers" % (self.exaile.get_settings_dir(),
                    os.sep))
                log(cover['filename'])

                try:
                    self.db.execute("UPDATE albums SET image=? WHERE album=? " \
                        "AND artist=?", (cover['md5'] + ".jpg", self.album,
                        self.artist))
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

    def __mouse_move(self, widget, event):
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

    def __item_activated(self, iconview, path):
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
        all = self.db.select("SELECT artist, album FROM tracks WHERE blacklisted=0"
            "ORDER BY artist, album")
        self.needs = dict()

        self.found = dict()
        count = 0
        for (artist, album) in all:
            if not self.needs.has_key(artist):
                self.needs[artist] = []
            if album in self.needs[artist]: continue
            row = self.db.read_one("albums", "image",
                "artist=? AND album=?", (artist, album))

            image = "images%snocover.png" % os.sep
            if not row or not row[0]:
                self.db.execute("REPLACE INTO albums(artist, " \
                "album) VALUES( ?, ? " \
                ")", (artist, album))
                self.needs[artist].append(album)
            elif row[0].find("nocover") > -1:
                self.needs[artist].append(album)
            elif row[0] and row[0].find("nocover") == -1: 
                image = "%s%scovers%s%s" % (self.exaile.get_settings_dir(),
                    os.sep, os.sep, row[0])

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

class NotebookTab(gtk.HBox):
    """
        Shows a close image on a notebook tab
    """
    def __init__(self, exaile, title, page):
        gtk.HBox.__init__(self, False, 5)
        self.title = title
        self.label = gtk.Label(title)
        
        box = gtk.EventBox()
        box.connect('button_press_event',
            self.close_tab)
        box.add(self.label)
        self.pack_start(self.wrapper(box), 
            False, False)
        self.tips = gtk.Tooltips()

        image = gtk.Image()
        image.set_from_file('images%sclose.png' % os.sep)
        self.pack_start(self.wrapper(image, True), False, False)
        self.page = page
        self.nb = exaile.playlists_nb
        self.exaile = exaile
        self.connect('button_press_event',
            self.close_tab)
        self.show_all()

    def wrapper(self, widget, close=False):
        """
            Wraps the specified widget in an event box
        """
        if close: 
            self.box = gtk.EventBox()
            self.tips.set_tip(self.box, _("Close this tab"))
            self.box.connect('button_press_event', self.close_tab)
            self.box.add(widget)
        else: self.box = widget
        return self.box

    def __rename(self, widget, event):
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

    def __save_playlist(self, widget, event):
        """
            Saves a playlist
        """
        songs = self.page.songs
        self.exaile.playlists_panel.on_add_playlist(widget, None, songs)

    def create_menu(self):
        """
            Creates the popup menu for this tab
        """
        menu = Menu()
        menu.append(_("Rename"), self.__rename)
        menu.append(_("Close"), lambda *e:
            self.exaile.close_page(self.page))

        if not isinstance(self.page, trackslist.QueueManager) and \
            not isinstance(self.page, trackslist.BlacklistedTracksList):
            menu.append(_("Save Playlist"), self.__save_playlist)
            
        self.menu = menu

    def close_tab(self, tab, event):
        """
            Closes the tab
        """
        if event.button == 3:
            self.create_menu()
            self.menu.popup(None, None, None, event.button, event.time)
        elif tab == self.box:
            self.exaile.close_page(self.page)

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
        self.dialog.connect('delete_event', self.__destroy)
        
        DebugDialog.debug = self

    def __destroy(self, *e):
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
            self.t = ThreadRunner(self.load_url)
            self.t.history = False
            self.t.url = url
            self.t.start()

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

    def load_url(self, thread):
        """
            Loads a URL, either from the cache, or from the website specified
        """

        if thread.history:
            self.history = self.history[:self.current + 1]
            self.history.append(thread.url)
            self.current = len(self.history) - 1
        url = thread.url
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
        self.page_loaded(url, data, True)

        if not self.nostyles:
            if self.history and thread.history:
                self.back.set_sensitive(True)

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
        self.t.stopped = True
        self.t = ThreadRunner(self.load_url)
        self.t.url = link
        self.t.history = history
        self.t.start()

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
        box.pack_start(image)
        window.set_title(title)
        window.set_transient_for(parent)
        window.show_all()

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
        self.prev.connect('clicked', self.__prev)
        self.prev.set_sensitive(False)
        self.next = self.xml.get_widget('cover_forward_button')
        self.next.connect('clicked', self.__next)
        self.xml.get_widget('cover_newsearch_button').connect('clicked',
            self.__new_search)
        self.xml.get_widget('cover_cancel_button').connect('clicked',
            lambda *e: self.window.destroy())
        self.ok = self.xml.get_widget('cover_ok_button')
        self.ok.connect('clicked',
            self.__ok)
        self.box = self.xml.get_widget('cover_image_box')
        self.cover = ImageWidget()
        self.cover.set_image_size(350, 350)
        self.box.pack_start(self.cover, True, True)

        self.last_search = "%s - %s" % (track.artist, track.album)

        if not search:
            covers.CoverFetcherThread("%s - %s" % (track.artist, track.album),
                self.__covers_fetched).start()
        else:
            self.__new_search()

    def __new_search(self, widget=None):
        """
            Creates a new search string
        """
        dialog = TextEntryDialog(self.exaile.window,
            _("Enter the search text"), _("Enter the search text"))
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_OK:
            self.last_search = dialog.get_value()
            self.exaile.status.set_first(
                _("Searching for ") + self.last_search + "...")
            self.window.hide()

            covers.CoverFetcherThread(self.last_search,
                self.__covers_fetched, True).start()

    def __ok(self, widget=None):
        """
            Chooses the current cover and saves it to the database
        """
        track = self.track
        cover = self.covers[self.current]
        row = self.db.read_one(
            "albums", "artist, album, genre, image",
            "artist=? AND album=?",
            (track.artist, track.album))

        self.db.update("albums",
            { "artist": track.artist,
            "album": track.album,
            "image": cover.filename(),
            "genre": track.genre }, "artist=? AND album=?",
            (track.artist, track.album), row == None)

        if track == self.exaile.current_track:
            self.exaile.stop_cover_thread()
            self.exaile.cover.set_image("%s%scovers%s%s" %
                (self.exaile.get_settings_dir(), os.sep, os.sep,
                cover.filename()))
        self.window.destroy()

    def __next(self, widget):
        """
            Shows the next cover
        """
        if self.current + 1 >= len(self.covers): return
        self.current = self.current + 1
        self.__show_cover(self.covers[self.current])
        if self.current + 1 >= len(self.covers):
            self.next.set_sensitive(False)
        if self.current - 1 >= 0:
            self.prev.set_sensitive(True)

    def __prev(self, widget):
        """
            Shows the previous cover
        """
        if self.current - 1 < 0: return
        self.current = self.current - 1
        self.__show_cover(self.covers[self.current])

        if self.current + 1 < len(self.covers):
            self.next.set_sensitive(True)
        if self.current - 1 < 0:
            self.prev.set_sensitive(False)

    def __show_cover(self, c):
        """
            Shows the current cover
        """
        c.save("%s%scovers%s" % (self.exaile.get_settings_dir(),
            os.sep, os.sep))

        log(c.filename())

        self.cover.set_image("%s%scovers%s%s" % (self.exaile.get_settings_dir(),
            os.sep, os.sep, c.filename()))

        self.window.show()

    def __covers_fetched(self, covers):
        """
            Called when the cover fetcher thread has fetched all covers
        """
        self.exaile.status.set_first(None)

        if len(covers) <= 0:
            common.error(self.exaile.window, _("Sorry, no covers were found."))
            self.covers = []
            self.next.set_sensitive(False)
            self.ok.set_sensitive(False)
            self.window.show()
            return

        if len(covers) > 1: self.next.set_sensitive(True)
        else: self.next.set_sensitive(False)
        self.ok.set_sensitive(True)

        self.covers = covers
        self.current = 0

        self.__show_cover(self.covers[self.current])

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
            self.__on_add)
        self.xml.get_widget('lm_remove_button').connect('clicked',
            self.__on_remove)

        self.xml.get_widget('lm_cancel_button').connect('clicked',
            lambda e: self.dialog.response(gtk.RESPONSE_CANCEL))
        self.xml.get_widget('lm_apply_button').connect('clicked',
            self.__on_apply)

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

    def __on_apply(self, widget):
        """
            Saves the paths in the dialog, and updates the library
        """
        self.exaile.settings['search_paths'] = ":".join(self.list.rows)
        self.dialog.response(gtk.RESPONSE_APPLY)

    def __on_remove(self, widget):
        """
            removes a path from the list
        """
        item = self.list.get_selection()
        self.list.remove(item)

    def __on_add(self, widget):
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

    def set_image(self, image):
        """
            Sets the image
        """
        self.loc = image
        pixbuf = gtk.gdk.pixbuf_new_from_file(image)
        scaled = pixbuf.scale_simple(self.size[0], self.size[1],
            gtk.gdk.INTERP_BILINEAR)
        self.set_from_pixbuf(scaled)
        scaled = pixbuf = None

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

class PopupWindow(object):
    """
        A popup window to show information on the current playing track
    """
    def __init__(self, exaile, settings, start_timer=True, draggable=False):
        """
            Initializes the popup
        """
        self.exaile = exaile
        self.draggable = draggable
        self.xml = gtk.glade.XML('exaile.glade', 'PopupWindow', 'exaile')
        self.window = self.xml.get_widget('PopupWindow')
        self.__timeout = None
        self.start_timer = start_timer

        color = gtk.gdk.color_parse(settings['osd_bgcolor'])
        self.settings = settings
        self.event = self.xml.get_widget('popup_event_box')
        self.box = self.xml.get_widget('image_box')
        self.window.modify_bg(gtk.STATE_NORMAL, color)
        self.title = self.xml.get_widget('popup_title_label')
        self.title.set_attributes(self.get_font_info(settings['osd_textcolor'],
            settings['osd_large_text_font']))

        attr = self.get_font_info(settings['osd_textcolor'],
            settings['osd_small_text_font'])

        self.artist = self.xml.get_widget('popup_artist_label')
        self.artist.set_attributes(attr)
        self.album = self.xml.get_widget('popup_album_label')
        self.album.set_attributes(attr)
        self.window.set_size_request(settings['osd_w'], settings['osd_h'])
        self.cover = ImageWidget()
        self.box.pack_start(self.cover, False, False)
        self.window.move(settings['osd_x'], settings['osd_y'])
        self.cover.set_image_size(settings['osd_h'] - 8, settings['osd_h'] - 8)
        self.event.connect('button_press_event', self.start_dragging)
        self.event.connect('button_release_event', self.stop_dragging)

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
        self.window.disconnect(self.__handler)
        if self.start_timer:
            self.__timeout = gobject.timeout_add(4000, self.window.hide)
        settings = self.exaile.settings
        (w, h) = self.window.get_size()
        (x, y) = self.window.get_position()

        settings['osd_x'] = x
        settings['osd_y'] = y
        settings['osd_h'] = h
        settings['osd_w'] = w
    
        POPUP = PopupWindow(self.exaile, get_popup_settings(settings))

    def dragging(self, widget, event):
        """
            Called when the user drags the window
        """
        self.window.move(int(event.x_root - self.__start[0]),
            int(event.y_root - self.__start[1]))

    def get_font_info(self, color, font):
        """
            Gets pango attributes for the specific arguments
        """
        attr = pango.AttrList()
        attr.change(pango.AttrFontDesc(pango.FontDescription(font), 0, 600))
        color = pango.Color(color)
        attr.change(pango.AttrForeground(color.red, color.green, color.blue,
        0, 600))
        return attr

    def show_popup(self, title, album, artist, cover):
        """
            Displays the popup for 4 seconds
        """
        if not title: title = "Unknown"
        if not album: album = "Unknown Album"
        if not artist: artist = "Unknown Artist"

        if self.__timeout:
            gobject.source_remove(self.__timeout)
            self.window.hide()
        self.title.set_label(title)
        self.album.set_label(album)
        self.artist.set_label(artist)

        if cover == None:
            cover = 'images%snocover.png' % os.sep

        self.cover.set_image(cover)
        self.window.show_all()

        if self.start_timer: 
            self.__timeout = gobject.timeout_add(4000, self.window.hide)

POPUP = None
def get_popup(exaile, settings):
    """
        Gets a popup instance
    """
    global POPUP
    
    if not POPUP:
        POPUP = PopupWindow(exaile, settings)

    return POPUP

def get_popup_settings(settings):
    info = dict()
    info['osd_bgcolor'] = settings.get("osd_bgcolor", "#567ea2")
    info['osd_textcolor'] = settings.get("osd_textcolor", "#ffffff")
    info['osd_w'] = settings.get_int("osd_w", 400)
    info['osd_h'] = settings.get_int("osd_h", 83)
    info['osd_y'] = settings.get_int("osd_y", 0)
    info['osd_x'] = settings.get_int("osd_x", 0)
    info['osd_large_text_font'] = settings.get("osd_large_text_font", 
        "Sans 14");
    info['osd_small_text_font'] = settings.get("osd_small_text_font", 
        "Sans 8");

    return info

try:
    import dbus
    DBUS_AVAIL = True
except:
    DBUS_AVAIL = False

def test_dbus(bus, interface):
    if not DBUS_AVAIL: return False
    obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus') 
    dbus_iface = dbus.Interface(obj, 'org.freedesktop.DBus') 
    avail = dbus_iface.ListNames() 
    return interface in avail
