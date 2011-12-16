# Copyright (C) 2010 Adam Olsen
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

import glib
import re
import gtk
from datetime import datetime
from xl.nls import gettext as _
from xl import event, settings, providers, xdg
from xl.playlist import Playlist, PlaylistManager
from xlgui.widgets import menu
from xlgui.accelerators import Accelerator
from xlgui.widgets.notebook import SmartNotebook, NotebookTab
from xlgui.widgets.playlist import PlaylistPage
from xlgui.widgets.queue import QueuePage

import logging
logger = logging.getLogger(__name__)

class PlaylistNotebook(SmartNotebook):
    def __init__(self, manager_name, player):
        SmartNotebook.__init__(self)
        self.tab_manager = PlaylistManager(manager_name)
        self.player = player
        
        # for saving closed tab history
        self.tab_history = []
        self.history_counter = 90000 # to get unique (reverse-ordered) item names

        # build static menu entries        
        item = menu.simple_separator('clear-sep',[])
        providers.register('playlist-closed-tab-menu', item)
        item = menu.simple_menu_item('clear-history', ['clear-sep'], _("Clear"), 'gtk-clear',
            self.clear_closed_tabs)
        providers.register('playlist-closed-tab-menu', item)     
            
        # simple factory for 'Recently Closed Tabs' MenuItem
        submenu = menu.ProviderMenu('playlist-closed-tab-menu',self)
        def factory(menu_, parent, context):
            item = gtk.MenuItem(_("Recently Closed Tabs"))
            if len(self.tab_history) > 0:
                item.set_submenu(submenu)
            else:
                item.set_sensitive(False)
            return item
            
        # add menu to tab context menu
        item = menu.MenuItem('tab-history', factory, ['tab-close'])
        providers.register('playlist-tab-context-menu', item)

        # add menu to View menu
        item = menu.MenuItem('tab-history', factory, ['clear-playlist'])
        providers.register('menubar-view-menu', item)       

        # add hotkey
        self.accelerator = Accelerator('<Control><Shift>t', lambda *x: self.restore_closed_tab(0))
        providers.register('mainwindow-accelerators',self.accelerator)

        self.load_saved_tabs()
        self.queuepage = QueuePage()
        self.queuetab = NotebookTab(self, self.queuepage)
        if len(self.player.queue) > 0:
            self.show_queue()

        self.tab_placement_map = {
            'left': gtk.POS_LEFT,
            'right': gtk.POS_RIGHT,
            'top': gtk.POS_TOP,
            'bottom': gtk.POS_BOTTOM
        }

        self.connect('page-added', self.on_page_added)
        self.connect('page-removed', self.on_page_removed)
        self.connect('page-reordered', self.on_page_reordered)

        self.on_option_set('gui_option_set', settings, 'gui/show_tabbar')
        self.on_option_set('gui_option_set', settings, 'gui/tab_placement')
        event.add_callback(self.on_option_set, 'gui_option_set')

    def show_queue(self, switch=True):
        if self.queuepage not in self.get_children():
            self.add_tab(self.queuetab, self.queuepage, position=0)
        if switch:
            # should always be 0, but doesn't hurt to be safe...
            self.set_current_page(self.page_num(self.queuepage))

    def create_tab_from_playlist(self, playlist):
        """
            Create a tab that will contain the passed-in playlist

            :param playlist: The playlist to create tab from
            :type playlist: :class:`xl.playlist.Playlist`
        """
        page = PlaylistPage(playlist, self.player)
        tab = NotebookTab(self, page)
        self.add_tab(tab, page)
        return tab

    def create_new_playlist(self):
        """
            Create a new tab containing a blank playlist.
            The tab will be automatically given a unique name.
        """
        seen = []
        default_playlist_name = _('Playlist %d')
        # Split into 'Playlist ' and ''
        default_name_parts = default_playlist_name.split('%d')

        for n in range(self.get_n_pages()):
            page = self.get_nth_page(n)
            name = page.get_name()
            name_parts = [
                # 'Playlist 99' => 'Playlist '
                name[0:len(default_name_parts[0])],
                # 'Playlist 99' => ''
                name[len(name) - len(default_name_parts[1]):]
            ]

            # Playlist name matches our format
            if name_parts == default_name_parts:
                # Extract possible number between name parts
                number = name[len(name_parts[0]):len(name) - len(name_parts[1])]

                try:
                    number = int(number)
                except ValueError:
                    pass
                else:
                    seen += [number]

        seen.sort()
        n = 1

        while True:
            if n not in seen:
                break
            n += 1

        playlist = Playlist(default_playlist_name % n)

        return self.create_tab_from_playlist(playlist)

    def add_default_tab(self):
        return self.create_new_playlist()

    def load_saved_tabs(self):
        names = self.tab_manager.list_playlists()
        if not names:
            self.add_default_tab()
            return

        count = -1
        count2 = 0
        names.sort()
        # holds the order#'s of the already added tabs
        added_tabs = {}
        name_re = re.compile(
                r'^order(?P<tab>\d+)\.(?P<tag>[^.]*)\.(?P<name>.*)$')
        for i, name in enumerate(names):
            match = name_re.match(name)
            if not match or not match.group('tab') or not match.group('name'):
                logger.error("%s did not match valid playlist file"
                        % repr(name))
                continue

            logger.debug("Adding playlist %d: %s" % (i, name))
            logger.debug("Tab:%s; Tag:%s; Name:%s" % (match.group('tab'),
                                                     match.group('tag'),
                                                     match.group('name'),
                                                     ))
            pl = self.tab_manager.get_playlist(name)
            pl.name = match.group('name')

            if match.group('tab') not in added_tabs:
                self.create_tab_from_playlist(pl)
                added_tabs[match.group('tab')] = pl
            pl = added_tabs[match.group('tab')]

            if match.group('tag') == 'current':
                count = i
                if self.player.queue.current_playlist is None:
                    self.player.queue.set_current_playlist(pl)
            elif match.group('tag') == 'playing':
                count2 = i
                self.player.queue.set_current_playlist(pl)

        # If there's no selected playlist saved, use the currently
        # playing
        if count == -1:
            count = count2

        self.set_current_page(count)

    def save_current_tabs(self):
        """
            Saves the open tabs
        """
        # first, delete the current tabs
        names = self.tab_manager.list_playlists()
        for name in names:
            logger.debug("Removing tab %s" % name)
            self.tab_manager.remove_playlist(name)

        # TODO: make this generic enough to save other kinds of tabs
        for n, page in enumerate(self):
            if not isinstance(page, PlaylistPage):
                continue

            tag = ''

            if page.playlist is self.player.queue.current_playlist:
                tag = 'playing'
            elif n == self.get_current_page():
                tag = 'current'

            page.playlist.name = 'order%d.%s.%s' % (n, tag, page.playlist.name)
            logger.debug('Saving tab %r', page.playlist.name)

            try:
                self.tab_manager.save_playlist(page.playlist, True)
            except Exception:
                # an exception here could cause exaile to be unable to quit.
                # Catch all exceptions.
                logger.exception("Error saving tab %r", page.playlist.name)

    def show_current_track(self):
        """
            Tries to find the currently playing track
            and selects it and its containing tab page
        """
        for n, page in enumerate(self):
            if not isinstance(page, PlaylistPage):
                continue

            if page.playlist is not self.player.queue.current_playlist:
                continue

            self.set_current_page(n)
            page.view.scroll_to_cell(page.playlist.current_position)
            page.view.set_cursor(page.playlist.current_position)

    def on_page_added(self, notebook, child, page_number):
        """
            Updates appearance on page add
        """
        if self.get_n_pages() > 1:
            # Enforce tabbar visibility
            self.set_show_tabs(True)

    def on_page_removed(self, notebook, child, page_number):
        """
            Updates appearance on page removal
        """
        if self.get_n_pages() == 1:
            self.set_show_tabs(settings.get_option('gui/show_tabbar', True))
            
        # closed tab history
        if settings.get_option('gui/save_closed_tabs', True) and \
            isinstance(child, PlaylistPage):
            self.save_closed_tab(child.playlist)

    def on_page_reordered(self, notebook, child, page_number):
        if self.page_num(self.queuepage) != 0:
            self.reorder_child(self.queuepage, 0)

    def restore_closed_tab(self, pos=None, playlist=None, item_name=None):
        ret = self.remove_closed_tab(pos, playlist, item_name)
        if ret is not None:
            self.create_tab_from_playlist(ret[0])

    def save_closed_tab(self, playlist):
        # don't let the list grow indefinitely
        items = providers.get('playlist-closed-tab-menu')
        if len(self.tab_history) > settings.get_option('gui/max_closed_tabs', 10):
            self.remove_closed_tab(-1) # remove last item
        
        item_name = 'playlist%05d'%self.history_counter 
        close_time = datetime.now()
        # define a MenuItem factory that supports dynamic labels
        def factory(menu_, parent, context):
            item = None
            
            dt = (datetime.now()-close_time)
            display_name = '{0} ({1} tracks, closed '.format(playlist.name, len(playlist))
            if dt.seconds > 60:
                display_name += '{0} min ago)'.format(dt.seconds//60 )
            else:
                display_name += '{0} sec ago)'.format(dt.seconds )
            item = gtk.ImageMenuItem(display_name)
            image = gtk.image_new_from_file(
                xdg.get_data_path('images/playlist.png'))
            item.set_image(image)

            # Add accelerator to top item
            if self.tab_history[0][1].name == item_name:
                key, mods = gtk.accelerator_parse(self.accelerator.keys)
                item.add_accelerator('activate', menu.FAKEACCELGROUP, key, mods,
                        gtk.ACCEL_VISIBLE)


            item.connect('activate', lambda w: self.restore_closed_tab(item_name=item_name))

            return item

        # create menuitem
        item = menu.MenuItem(item_name, factory, [])
        providers.register('playlist-closed-tab-menu', item)
        self.history_counter -= 1
        
        # add
        self.tab_history.insert(0, (playlist,item))
        
    def get_closed_tab(self, pos=None, playlist=None, item_name=None):
        if pos is not None:
            try:
                return self.tab_history[pos]
            except IndexError:
                return None
        elif playlist is not None:
            for (pl, item) in self.tab_history:
                if pl == playlist:
                    return (pl, item)
        elif item_name is not None:
            for (pl, item) in self.tab_history:
                if item.name == item_name:
                    return (pl, item)

        return None                
        # remove from menus
        
    def remove_closed_tab(self, pos=None, playlist=None, item_name=None):
        ret = self.get_closed_tab(pos, playlist, item_name)
        if ret is not None:
            self.tab_history.remove(ret)
            providers.unregister('playlist-closed-tab-menu', ret[1])
        return ret

    def clear_closed_tabs(self, widget, name, parent, context):
        for i in xrange(len(self.tab_history)):
            self.remove_closed_tab(0)


    def on_option_set(self, event, settings, option):
        """
            Updates appearance on setting change
        """
        if option == 'gui/show_tabbar':
            show_tabbar = settings.get_option(option, True)

            if not show_tabbar and self.get_n_pages() > 1:
                show_tabbar = True

            glib.idle_add(self.set_show_tabs, show_tabbar)

        if option == 'gui/tab_placement':
            tab_placement = settings.get_option(option, 'top')
            glib.idle_add(self.set_tab_pos, self.tab_placement_map[tab_placement])

