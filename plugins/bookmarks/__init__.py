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

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
import os
import logging
logger = logging.getLogger(__name__)

from xl import (
    covers,
    event,
    player,
    settings,
    trax,
    xdg,
    providers
)
from xl.nls import gettext as _
from xlgui import guiutil, icons
from xlgui.widgets import dialogs, menu

import bookmarksprefs

# We want to use json to write bookmarks to files, cuz it's prettier (and safer)
# if we're on python 2.5 it's not available...
try:
    import json

    def _try_read(data):
        # try reading using json, if it fails, try the old format
        try:
            return json.loads(data)
        except ValueError:
            return eval(data, {'__builtin__': None})

    _write = lambda x: json.dumps(x, indent=2)
    _read = _try_read

except ImportError:
    _write = str
    _read = lambda x: eval(x, {'__builtin__': None})


_smi = menu.simple_menu_item
_sep = menu.simple_separator

# TODO: to dict or not to dict.  dict prevents duplicates, list of tuples preserves order (using tuples atm)
# does order matter?


def error(text):
    logger.error("%s: %s" % ('Bookmarks', text))
    dialogs.error(None, exaile.gui.main, text)


class Bookmarks:

    def __init__(self, exaile):
        self.bookmarks = []
#        self.auto_db = {}
        self.exaile = exaile
        self.use_covers = settings.get_option('plugin/bookmarks/use_covers', False)
        self.counter = 0

        # setup menus
        self.menu = menu.Menu(self)
        self.delete_menu = menu.Menu(self)

        # define factory-factory for sensitive-aware menuitems
        def factory_factory(display_name, icon_name, callback=None, submenu=None):
            def factory(menu_, parent, context):
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
        items.append(menu.MenuItem('delete', factory_factory(_('_Delete Bookmark'),
                                                             'gtk-close', submenu=self.delete_menu), ['bookmark']))
        items.append(menu.MenuItem('clear', factory_factory(_('_Clear Bookmarks'),
                                                            'gtk-clear', callback=self.clear), ['delete']))
        items.append(_sep('sep', ['clear']))

        for item in items:
            self.menu.add_item(item)

        # TODO: automatic bookmarks, not yet possible
        #  - needs a way to get the time a file is inturrupted at
        # set events - not functional yet
        #event.add_callback(self.on_start_track, 'playback_start')
        #event.add_callback(self.on_stop_track, 'playback_end')
        #playback_end, playback_pause, playback_resume, stop_track

    def do_bookmark(self, widget, data):
        """
            This is called to resume a bookmark.
        """
        key, pos = data
        exaile = self.exaile

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
            if track:   # make sure we got one
                player.QUEUE.play(track)
                player.PLAYER.seek(pos)

    def add_bookmark(self, *args):
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

    def display_bookmark(self, key, pos):
        """
            Create menu entrees for this bookmark.
        """
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
                        logger.warn('Could not load cover')
                        pix = None
                        # no cover
                else:
                    pix = None
        except Exception:
            logger.exception("Cannot open %s", key)
            # delete offending key?
            return
        time = '%d:%02d' % (pos / 60, pos % 60)
        label = '%s @ %s' % (title, time)

        counter = self.counter  # closure magic (workaround for factories not having access to item)
        # factory for new bookmarks

        def factory(menu_, parent, context):
            menu_item = Gtk.ImageMenuItem.new_with_mnemonic(label)
            if pix:
                menu_item.set_image(Gtk.image_new_from_pixbuf(pix))

            if menu_ is self.menu:
                menu_item.connect('activate', self.do_bookmark, (key, pos))
            else:
                menu_item.connect('activate', self.delete_bookmark, (counter, key, pos))

            return menu_item

        item = menu.MenuItem('bookmark{0}'.format(self.counter), factory, ['sep'])
        self.menu.add_item(item)
        self.delete_menu.add_item(item)

        self.counter += 1

        # save addition
        self.save_db()

    def clear(self, widget):
        """
            Delete all bookmarks.
        """
        # remove from menus
        for item in self.delete_menu._items:
            self.menu.remove_item(item)
            self.delete_menu.remove_item(item)

        self.bookmarks = []
        self.save_db()

    def delete_bookmark(self, widget, targets):
        """
            Delete a bookmark.
        """
        # print targets
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

    def load_db(self):
        """
            Load previously saved bookmarks from a file.
        """
        path = os.path.join(xdg.get_data_dirs()[0], 'bookmarklist.dat')
        try:
            # Load Bookmark List from file.
            with open(path, 'rb') as f:
                data = f.read()
                try:
                    db = _read(data)
                    for (key, pos) in db:
                        self.bookmarks.append((key, pos))
                        self.display_bookmark(key, pos)
                    logger.debug('loaded {0} bookmarks'.format(len(db)))
                except Exception as s:
                    logger.error('BM: bad bookmark file: %s' % s)
                    return None

        except IOError as e:  # File might not exist
            logger.error('BM: could not open file: %s' % e.strerror)

    def save_db(self):
        """
            Save list of bookmarks to a file.
        """
        # Save List
        path = os.path.join(xdg.get_data_dirs()[0], 'bookmarklist.dat')
        with open(path, 'wb') as f:
            f.write(_write(self.bookmarks))
            logger.debug('saving {0} bookmarks'.format(len(self.bookmarks)))


def __enb(eventname, exaile, nothing):
    GLib.idle_add(_enable, exaile)


def enable(exaile):
    """
        Dummy initialization function, calls _enable when exaile is fully loaded.
    """

    if exaile.loading:
        event.add_callback(__enb, 'gui_loaded')
    else:
        __enb(None, exaile, None)


def _enable(exaile):
    """
        Called when plugin is enabled.  Set up the menus, create the bookmark class, and
        load any saved bookmarks.
    """

    bm = Bookmarks(exaile)

    # add tools menu items
    providers.register('menubar-tools-menu', _sep('plugin-sep', ['track-properties']))

    item = _smi('bookmarks', ['plugin-sep'], _('_Bookmarks'),
                'user-bookmarks', submenu=bm.menu)
    providers.register('menubar-tools-menu', item)

    bm.load_db()


def disable(exaile):
    """
        Called when the plugin is disabled.  Destroy menu.
    """
    for item in providers.get('menubar-tools-menu'):
        if item.name == 'bookmarks':
            providers.unregister('menubar-tools-menu', item)
            break


# vi: et ts=4 sts=4 sw=4
def get_preferences_pane():
    return bookmarksprefs
