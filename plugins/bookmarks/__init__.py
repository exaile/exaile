# Bookmark plugin for Exaile media player
# Copyright (C) 2009-2011 Brian Parma
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import copy
import json
import logging
import os
import threading

from gi.repository import GLib
from gi.repository import Gtk

from xl import covers, player, trax, xdg, providers
from xl import common
from xl.nls import gettext as _
import xlgui
from xlgui.guiutil import pixbuf_from_data
from xlgui.widgets import dialogs, menu


LOGGER = logging.getLogger(__name__)


_smi = menu.simple_menu_item
_sep = menu.simple_separator


class Bookmark:
    """
    Manages a bookmark and provides a method to create a menu item.
    """

    __counter = 0

    def __init__(
        self, bookmarks_menu, delete_menu, delete_bookmark_callback, path, time
    ):
        """
        Creates a bookmark for current track/position if path or time are
        None. Creates a bookmark for the given track/positon otherwise.
        """
        if not path:
            # get currently playing track
            track = player.PLAYER.current
            if track is None:
                text = 'Need a playing track to Bookmark.'
                LOGGER.error(text)
                dialogs.error(xlgui.main.mainwindow(), text)
                return
            time = player.PLAYER.get_time()
            path = track.get_loc_for_io()

        self.__path = path
        self.__time = time
        self.__title = None
        self.__cover_pixbuf = None
        self.item = None

        self.__fetch_metadata()
        self.__create_menu_item(bookmarks_menu, delete_menu, delete_bookmark_callback)

    def get_menu_item(self):
        return self.item

    def __fetch_metadata(self, *_args):
        # "gtk-menu-images" is deprecated and is being ignored on most
        # platforms. On GNOME/Wayland it can be enabled by editing
        # ~/.config/gtk-3.0/settings.ini and adding `gtk-menu-images=1`.
        use_covers = Gtk.Settings.get_default().props.gtk_menu_images

        try:
            item = trax.Track(self.__path)
            if not self.__title:
                self.__title = item.get_tag_display('title')
            if use_covers:
                image = covers.MANAGER.get_cover(item, set_only=True)
                if image:
                    try:
                        self.__cover_pixbuf = pixbuf_from_data(image, size=(16, 16))
                    except GLib.GError:
                        LOGGER.warning('Could not load cover')
            else:
                self.__cover_pixbuf = None
        except Exception:
            LOGGER.exception("Cannot open %s", self.__path)
            return

    def __create_menu_item(self, bookmarks_menu, delete_menu, delete_bookmark_callback):
        """
        Create menu entries for this bookmark.
        """
        time = '%d:%02d' % (self.__time // 60, self.__time % 60)
        label = '%s @ %s' % (self.__title, time)

        def factory(menu_, _parent, _context):
            "menu factory for new bookmarks"
            menu_item = Gtk.ImageMenuItem.new_with_mnemonic(label)
            if self.__cover_pixbuf:
                menu_item.set_image(Gtk.Image.new_from_pixbuf(self.__cover_pixbuf))

            if menu_ is bookmarks_menu:
                menu_item.connect('activate', self.__on_bookmark_activated)
            else:
                menu_item.connect('activate', delete_bookmark_callback, self)

            return menu_item

        item = menu.MenuItem('bookmark{0}'.format(Bookmark.__counter), factory, ['sep'])
        Bookmark.__counter += 1
        bookmarks_menu.add_item(item)
        delete_menu.add_item(item)
        self.item = item

    def __on_bookmark_activated(self, _widget):
        """
        This is called to resume a bookmark.
        """
        # check if it's already playing
        track = player.PLAYER.current
        if track and track.get_loc_for_io() == self.__path:
            player.PLAYER.unpause()
            player.PLAYER.seek(self.__time)
        else:
            # play it using the QUEUE
            track = trax.Track(self.__path)
            if track:  # make sure we got one
                player.QUEUE.play(track)
                player.PLAYER.seek(self.__time)

    def serialize_bookmark(self):
        """
        Serializes a bookmark object for json.dump().
        This function assumes that a bookmark argument can be used as if
        it was given as self. This assumption might be wrong in the future.
        """
        if not isinstance(self, Bookmark):
            raise ValueError()
        return (self.__path, self.__time)


class BookmarksManager:
    """
    Manages a list of bookmarks and the associated menu entries
    """

    __PATH = os.path.join(xdg.get_data_dirs()[0], 'bookmarklist.dat')

    def __init__(self):
        self.__db_file_lock = threading.RLock()
        self.__bookmarks = []
        # self.auto_db = {}

        self.menu = None
        self.delete_menu = None
        self.__setup_menu()

        # TODO: automatic bookmarks, not yet possible
        #  - needs a way to get the time a file is interrupted at
        # set events - not functional yet
        # event.add_callback(self.on_start_track, 'playback_start')
        # event.add_callback(self.on_stop_track, 'playback_end')
        # playback_end, playback_pause, playback_resume, stop_track

        self.__load_db()

    def __setup_menu(self):
        self.menu = menu.Menu(self)
        self.delete_menu = menu.Menu(self)

        def factory_factory(display_name, icon_name, callback=None, submenu=None):
            "define factory-factory for sensitive-aware menuitems"

            def factory(_menu, _parent, _context):
                item = Gtk.ImageMenuItem.new_with_mnemonic(display_name)
                image = Gtk.Image.new_from_icon_name(icon_name, size=Gtk.IconSize.MENU)
                item.set_image(image)

                if callback is not None:
                    item.connect('activate', callback)
                if submenu is not None:
                    item.set_submenu(submenu)
                    # insensitive if no bookmarks present
                    if len(self.__bookmarks) == 0:
                        item.set_sensitive(False)
                return item

            return factory

        items = []
        items.append(
            _smi(
                'bookmark',
                [],
                _('_Bookmark This Track'),
                'bookmark-new',
                self.__on_add_bookmark,
            )
        )
        delete_cb = factory_factory(
            _('_Delete Bookmark'), 'gtk-close', submenu=self.delete_menu
        )
        items.append(menu.MenuItem('delete', delete_cb, ['bookmark']))
        clear_cb = factory_factory(
            _('_Clear Bookmarks'), 'gtk-clear', callback=self.__clear_bookmarks
        )
        items.append(menu.MenuItem('clear', clear_cb, ['delete']))
        items.append(_sep('sep', ['clear']))

        for item in items:
            self.menu.add_item(item)

    def __on_add_bookmark(self, _widget, _name, _foo, _bookmarks_manager):
        self.__add_bookmark()

    def __add_bookmark(self, path=None, time=None, save_db=True):
        if not self.menu:
            return  # this plugin is shutting down
        bookmark = Bookmark(
            self.menu, self.delete_menu, self.__delete_bookmark, path, time
        )
        self.__bookmarks.append(bookmark)
        if save_db:
            self.__save_db()

    def __clear_bookmarks(self, _widget):
        """
        Delete all bookmarks.
        """
        for bookmark in self.__bookmarks:
            self.delete_menu.remove_item(bookmark.get_menu_item())
            self.menu.remove_item(bookmark.get_menu_item())
        self.__bookmarks = []
        self.__save_db()

    def __delete_bookmark(self, _widget, bookmark):
        """
        Delete a bookmark.
        """
        self.__bookmarks.remove(bookmark)
        self.delete_menu.remove_item(bookmark.get_menu_item())
        self.menu.remove_item(bookmark.get_menu_item())
        self.__save_db()

    @common.threaded
    def __load_db(self):
        """
        Load previously saved bookmarks from a file.
        """
        with self.__db_file_lock:
            if not os.path.exists(self.__PATH):
                LOGGER.info('Bookmarks file does not exist yet.')
                return
            try:
                # NOTE: both binary and non-binary works here; use
                # non-binary to be consistent with open() call in
                # __do_save_db(), which needs to be non-binary
                with open(self.__PATH, 'r') as bm_file:
                    bookmarks = json.load(bm_file)
                    self.__load_db_callback(bookmarks)
            except IOError as err:
                LOGGER.error('BM: could not open file: %s', err.strerror)

    @common.idle_add()
    def __load_db_callback(self, loaded_bookmarks):
        if not self.menu:
            return  # this plugin is shutting down

        for (key, pos) in loaded_bookmarks:
            self.__add_bookmark(key, pos, save_db=False)

    def __save_db(self):
        """
        Save list of bookmarks to a file.
        """
        # lists are not thread-safe, so we need a copy.
        # we don't need a deep copy because keys and values are not mutated.
        bookmarks = copy.copy(self.__bookmarks)
        # cannot use common.threaded here because it must not be daemonized,
        # otherwise we might loose data on program shutdown.
        thread = threading.Thread(target=self.__do_save_db, args=[bookmarks])
        thread.daemon = False
        thread.start()

    def __do_save_db(self, bookmarks):
        with self.__db_file_lock:
            # NOTE: intentionally open in non-binary mode because
            # otherwise json.dump() throws an error about trying to
            # write an str instead of bytes
            with open(self.__PATH, 'w') as bm_file:
                json.dump(
                    bookmarks, bm_file, indent=2, default=Bookmark.serialize_bookmark
                )
            LOGGER.debug('saved %d bookmarks', len(bookmarks))


class BookmarksPlugin:
    def __init__(self):
        self.__manager = None

    def enable(self, exaile):
        pass

    def on_gui_loaded(self):
        """
        Called when plugin is enabled.  Set up the menus, create the bookmark class, and
        load any saved bookmarks.
        """

        self.__manager = BookmarksManager()

        # add tools menu items
        providers.register(
            'menubar-tools-menu', _sep('plugin-sep', ['track-properties'])
        )
        item = _smi(
            'bookmarks',
            ['plugin-sep'],
            _('_Bookmarks'),
            'user-bookmarks',
            submenu=self.__manager.menu,
        )
        providers.register('menubar-tools-menu', item)

    def disable(self, _exaile):
        """
        Called when the plugin is disabled.  Destroy menu.
        """
        self.__manager.menu = None  # used to mark plugin shutdown to display_bookmark
        for item in providers.get('menubar-tools-menu'):
            if item.name == 'bookmarks':
                providers.unregister('menubar-tools-menu', item)
                break
        self.__manager = None


plugin_class = BookmarksPlugin

# vi: et ts=4 sts=4 sw=4
