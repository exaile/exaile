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

from __future__ import with_statement

import json
import logging
import os

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from xl import (
    covers,
    event,
    player,
    settings,
    trax,
    xdg,
    providers
)
from xl.main import common
from xl.nls import gettext as _
import xlgui
from xlgui import guiutil, icons
from xlgui.widgets import dialogs, menu

import bookmarksprefs


LOGGER = logging.getLogger(__name__)


_smi = menu.simple_menu_item
_sep = menu.simple_separator


def error(text):
    LOGGER.error("%s: %s", 'Bookmarks', text)
    dialogs.error(xlgui.main.mainwindow(), text)


class Bookmarks:
    __PATH = os.path.join(xdg.get_data_dirs()[0], 'bookmarklist.dat')

    def __init__(self):
        self.bookmarks = []
#        self.auto_db = {}
        self.use_covers = settings.get_option('plugin/bookmarks/use_covers', False)
        self.counter = 0

        # setup menus
        self.menu = menu.Menu(self)
        self.delete_menu = menu.Menu(self)

        # define factory-factory for sensitive-aware menuitems
        def factory_factory(display_name, icon_name, callback=None, submenu=None):
            def factory(_menu, _parent, _context):
                item = Gtk.ImageMenuItem.new_with_mnemonic(display_name)
                image = Gtk.Image.new_from_icon_name(icon_name,
                                                     size=Gtk.IconSize.MENU)
                item.set_image(image)

                # insensitive if no bookmarks present
                if len(self.bookmarks) == 0:
                    item.set_sensitive(False)
                else:
                    if callback is not None:
                        item.connect('activate', callback)
                    if submenu is not None:
                        item.set_submenu(submenu)
                return item

            return factory

        items = []
        items.append(_smi('bookmark', [], _('_Bookmark This Track'),
                          'bookmark-new', self.add_bookmark))
        delete_cb = factory_factory(_('_Delete Bookmark'), 'gtk-close', submenu=self.delete_menu)
        items.append(menu.MenuItem('delete', delete_cb, ['bookmark']))
        clear_cb = factory_factory(_('_Clear Bookmarks'), 'gtk-clear', callback=self.clear)
        items.append(menu.MenuItem('clear', clear_cb, ['delete']))
        items.append(_sep('sep', ['clear']))

        for item in items:
            self.menu.add_item(item)

        # TODO: automatic bookmarks, not yet possible
        #  - needs a way to get the time a file is interrupted at
        # set events - not functional yet
        # event.add_callback(self.on_start_track, 'playback_start')
        # event.add_callback(self.on_stop_track, 'playback_end')
        # playback_end, playback_pause, playback_resume, stop_track
        self.load_db()

    @staticmethod
    def do_bookmark(_widget, data):
        """
            This is called to resume a bookmark.
        """
        key, pos = data

        if not (key and pos):
            return

        # check if it's already playing
        track = player.PLAYER.current
        if track and track.get_loc_for_io() == key:
            player.PLAYER.unpause()
            player.PLAYER.seek(pos)
            return
        else:
            # play it using the QUEUE
            track = trax.Track(key)
            if track:  # make sure we got one
                player.QUEUE.play(track)
                player.PLAYER.seek(pos)

    def add_bookmark(self, *_args):
        """
            Create bookmark for current track/position.
        """
        # get currently playing track
        track = player.PLAYER.current
        if track is None:
            error('Need a playing track to Bookmark.')
            return

        pos = player.PLAYER.get_time()
        key = track.get_loc_for_io()
        self.bookmarks.append((key, pos))
        self.display_bookmark(key, pos)

    @common.idle_add()
    def display_bookmark(self, key, pos):
        """
            Create menu entries for this bookmark.
            Fetching metadata requires disk access and may take a while,
            thus this function must be run on common.idle_add
        """
        if not self.menu:
            return  # this plugin is shutting down

        pix = None
        # add menu item
        try:
            item = trax.Track(key)
            title = item.get_tag_display('title')
            if self.use_covers:
                image = covers.MANAGER.get_cover(item, set_only=True)
                if image:
                    try:
                        pix = icons.MANAGER.pixbuf_from_data(image, size=(16, 16))
                    except GLib.GError:
                        LOGGER.warning('Could not load cover')
                        pix = None
                        # no cover
                else:
                    pix = None
        except Exception:
            LOGGER.exception("Cannot open %s", key)
            # delete offending key?
            return
        time = '%d:%02d' % (pos / 60, pos % 60)
        label = '%s @ %s' % (title, time)

        counter = self.counter  # closure magic (workaround for factories not having access to item)
        # factory for new bookmarks

        def factory(menu_, _parent, _context):
            menu_item = Gtk.ImageMenuItem.new_with_mnemonic(label)
            if pix:
                menu_item.set_image(Gtk.Image.new_from_pixbuf(pix))

            if menu_ is self.menu:
                menu_item.connect('activate', self.do_bookmark, (key, pos))
            else:
                menu_item.connect('activate', self.delete_bookmark, (counter, key, pos))

            return menu_item

        item = menu.MenuItem('bookmark{0}'.format(self.counter), factory, ['sep'])
        self.menu.add_item(item)
        self.delete_menu.add_item(item)

        self.counter += 1

    def clear(self, _widget):
        """
            Delete all bookmarks.
        """
        # remove from menus
        for item in self.delete_menu._items:
            self.menu.remove_item(item)
            self.delete_menu.remove_item(item)

        self.bookmarks = []
        self.save_db()

    def delete_bookmark(self, _widget, targets):
        """
            Delete a bookmark.
        """
        counter, key, pos = targets

        if (key, pos) in self.bookmarks:
            self.bookmarks.remove((key, pos))

        name = 'bookmark{0}'.format(counter)
        for item in self.delete_menu._items:
            if item.name == name:
                self.delete_menu.remove_item(item)
                self.menu.remove_item(item)
                break

        self.save_db()

    @common.idle_add()
    def load_db(self):
        """
            Load previously saved bookmarks from a file.
        """
        if not self.menu:
            return  # this plugin is shutting down

        if not os.path.exists(self.__PATH):
            LOGGER.info('Bookmarks file does not exist yet.')
            return None

        try:
            with open(self.__PATH, 'rb') as bm_file:
                self.bookmarks = json.load(bm_file)
            for (key, pos) in self.bookmarks:
                self.display_bookmark(key, pos)
        except IOError as err:
            LOGGER.error('BM: could not open file: %s', err.strerror)

    def save_db(self):
        """
            Save list of bookmarks to a file.
        """
        # Save List
        with open(self.__PATH, 'wb') as bm_file:
            json.dump(self.bookmarks, bm_file, indent=2)
        LOGGER.debug('saved %s bookmarks', len(self.bookmarks))


class BookmarksPlugin(object):

    def __init__(self):
        self.__bookmarks = None

    def enable(self, exaile):
        pass

    def on_gui_loaded(self):
        """
            Called when plugin is enabled.  Set up the menus, create the bookmark class, and
            load any saved bookmarks.
        """

        self.__bookmarks = Bookmarks()

        # add tools menu items
        providers.register('menubar-tools-menu', _sep('plugin-sep', ['track-properties']))
        item = _smi('bookmarks', ['plugin-sep'], _('_Bookmarks'),
                    'user-bookmarks', submenu=self.__bookmarks.menu)
        providers.register('menubar-tools-menu', item)

    def disable(self, _exaile):
        """
            Called when the plugin is disabled.  Destroy menu.
        """
        for item in providers.get('menubar-tools-menu'):
            if item.name == 'bookmarks':
                providers.unregister('menubar-tools-menu', item)
                break
        self.__bookmarks.menu = None  # used to mark plugin shutdown to display_bookmark
        self.__bookmarks = None

    def get_preferences_pane(self):
        return bookmarksprefs


plugin_class = BookmarksPlugin

# vi: et ts=4 sts=4 sw=4
