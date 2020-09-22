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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

from gi.repository import Gdk
from gi.repository import Gtk

import re
from datetime import datetime
from typing import List

from xl.nls import gettext as _
from xl import event, providers, settings
from xl.playlist import Playlist, PlaylistManager
from xlgui.widgets import menu
from xlgui.accelerators import Accelerator
from xlgui.widgets.notebook import (
    SmartNotebook,
    NotebookTab,
    NotebookAction,
    NotebookActionService,
)
from xlgui.widgets.playlist import PlaylistPage
from xlgui.widgets.queue import QueuePage

import logging

logger = logging.getLogger(__name__)


class NewPlaylistNotebookAction(NotebookAction, Gtk.Button):
    """
    Playlist notebook action which allows for creating new playlists
    regularly as well as by dropping tracks, files and directories on it
    """

    __gsignals__ = {'clicked': 'override'}
    name = 'new-playlist'
    position = Gtk.PackType.START

    def __init__(self, notebook):
        NotebookAction.__init__(self, notebook)
        Gtk.Button.__init__(self)

        self.set_image(Gtk.Image.new_from_icon_name('tab-new', Gtk.IconSize.BUTTON))
        self.set_relief(Gtk.ReliefStyle.NONE)

        self.__default_tooltip_text = _('New Playlist')
        self.__drag_tooltip_text = _('Drop here to create a new playlist')
        self.set_tooltip_text(self.__default_tooltip_text)

        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_add_uri_targets()

        self.connect('drag-motion', self.on_drag_motion)
        self.connect('drag-leave', self.on_drag_leave)
        self.connect('drag-data-received', self.on_drag_data_received)

    def do_clicked(self):
        """
        Triggers creation of a new playlist
        """
        self.notebook.create_new_playlist()

    def on_drag_motion(self, widget, context, x, y, time):
        """
        Updates the tooltip during drag operations
        """
        self.set_tooltip_text(self.__drag_tooltip_text)

    def on_drag_leave(self, widget, context, time):
        """
        Restores the original tooltip
        """
        self.set_tooltip_text(self.__default_tooltip_text)

    def on_drag_data_received(self, widget, context, x, y, selection, info, time):
        """
        Handles dropped data
        """
        tab = self.notebook.create_new_playlist()
        # Forward signal to the PlaylistView in the newly added tab
        tab.page.view.emit('drag-data-received', context, x, y, selection, info, time)


providers.register('playlist-notebook-actions', NewPlaylistNotebookAction)


class PlaylistNotebook(SmartNotebook):
    def __init__(self, manager_name, player, hotkey):
        SmartNotebook.__init__(self)

        self.tab_manager = PlaylistManager(manager_name)
        self.manager_name = manager_name
        self.player = player

        # For saving closed tab history
        self._moving_tab = False
        self.tab_history = []
        self.history_counter = 90000  # to get unique (reverse-ordered) item names

        # Build static menu entries
        item = menu.simple_separator('clear-sep', [])
        item.register('playlist-closed-tab-menu', self)

        item = menu.simple_menu_item(
            'clear-history',
            ['clear-sep'],
            _("_Clear Tab History"),
            'edit-clear-all',
            self.clear_closed_tabs,
        )
        item.register('playlist-closed-tab-menu', self)

        # Simple factory for 'Recently Closed Tabs' MenuItem
        submenu = menu.ProviderMenu('playlist-closed-tab-menu', self)

        def factory(menu_, parent, context):
            if self.page_num(parent) == -1:
                return None
            item = Gtk.MenuItem.new_with_mnemonic(_("Recently Closed _Tabs"))
            if len(self.tab_history) > 0:
                item.set_submenu(submenu)
            else:
                item.set_sensitive(False)
            return item

        # Add menu to tab context menu
        item = menu.MenuItem('%s-tab-history' % manager_name, factory, ['tab-close'])
        item.register('playlist-tab-context-menu')

        # Add menu to View menu
        # item = menu.MenuItem('tab-history', factory, ['clear-playlist'])
        # providers.register('menubar-view-menu', item)

        # setup notebook actions
        self.actions = NotebookActionService(self, 'playlist-notebook-actions')

        # Add hotkey
        self.accelerator = Accelerator(
            hotkey, _('Restore closed tab'), lambda *x: self.restore_closed_tab(0)
        )
        providers.register('mainwindow-accelerators', self.accelerator)

        # Load saved tabs
        self.load_saved_tabs()

        self.tab_placement_map = {
            'left': Gtk.PositionType.LEFT,
            'right': Gtk.PositionType.RIGHT,
            'top': Gtk.PositionType.TOP,
            'bottom': Gtk.PositionType.BOTTOM,
        }

        self.connect('page-added', self.on_page_added)
        self.connect('page-removed', self.on_page_removed)

        self.on_option_set('gui_option_set', settings, 'gui/show_tabbar')
        self.on_option_set('gui_option_set', settings, 'gui/tab_placement')
        event.add_ui_callback(self.on_option_set, 'gui_option_set')

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
            name = page.get_page_name()
            name_parts = [
                # 'Playlist 99' => 'Playlist '
                name[0 : len(default_name_parts[0])],
                # 'Playlist 99' => ''
                name[len(name) - len(default_name_parts[1]) :],
            ]

            # Playlist name matches our format
            if name_parts == default_name_parts:
                # Extract possible number between name parts
                number = name[len(name_parts[0]) : len(name) - len(name_parts[1])]

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
            return

        count = -1
        count2 = 0
        names.sort()
        # holds the order#'s of the already added tabs
        added_tabs = {}
        name_re = re.compile(r'^order(?P<tab>\d+)\.(?P<tag>[^.]*)\.(?P<name>.*)$')
        for i, name in enumerate(names):
            match = name_re.match(name)
            if not match or not match.group('tab') or not match.group('name'):
                logger.error("`%r` did not match valid playlist file", name)
                continue

            logger.debug("Adding playlist %d: %s", i, name)
            logger.debug(
                "Tab:%s; Tag:%s; Name:%s",
                match.group('tab'),
                match.group('tag'),
                match.group('name'),
            )
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
            logger.debug("Removing tab %s", name)
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
            return True

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
        if not self._moving_tab:

            if settings.get_option('gui/save_closed_tabs', True) and isinstance(
                child, PlaylistPage
            ):
                self.save_closed_tab(child.playlist)

            # Destroy it unless it's the queue page
            if not isinstance(child, QueuePage):
                child.destroy()

    def restore_closed_tab(self, pos=None, playlist=None, item_name=None):
        ret = self.remove_closed_tab(pos, playlist, item_name)
        if ret is not None:
            self.create_tab_from_playlist(ret[0])

    def save_closed_tab(self, playlist):
        # don't let the list grow indefinitely
        if len(self.tab_history) > settings.get_option('gui/max_closed_tabs', 10):
            self.remove_closed_tab(-1)  # remove last item

        item_name = 'playlist%05d' % self.history_counter
        close_time = datetime.now()
        # define a MenuItem factory that supports dynamic labels

        def factory(menu_, parent, context):
            item = None

            dt = datetime.now() - close_time
            if dt.seconds > 60:
                display_name = _(
                    '{playlist_name} ({track_count} tracks, closed {minutes} min ago)'
                ).format(
                    playlist_name=playlist.name,
                    track_count=len(playlist),
                    minutes=dt.seconds // 60,
                )
            else:
                display_name = _(
                    '{playlist_name} ({track_count} tracks, closed {seconds} sec ago)'
                ).format(
                    playlist_name=playlist.name,
                    track_count=len(playlist),
                    seconds=dt.seconds,
                )
            item = Gtk.ImageMenuItem.new_with_mnemonic(display_name)
            item.set_image(
                Gtk.Image.new_from_icon_name('music-library', Gtk.IconSize.MENU)
            )

            # Add accelerator to top item
            if self.tab_history[0][1].name == item_name:
                key, mods = Gtk.accelerator_parse(self.accelerator.keys)
                item.add_accelerator(
                    'activate', menu.FAKEACCELGROUP, key, mods, Gtk.AccelFlags.VISIBLE
                )

            item.connect(
                'activate', lambda w: self.restore_closed_tab(item_name=item_name)
            )

            return item

        # create menuitem
        item = menu.MenuItem(item_name, factory, [])
        providers.register('playlist-closed-tab-menu', item, self)
        self.history_counter -= 1

        # add
        self.tab_history.insert(0, (playlist, item))

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
            providers.unregister('playlist-closed-tab-menu', ret[1], self)
        return ret

    def clear_closed_tabs(self, widget, name, parent, context):
        for i in range(len(self.tab_history)):
            self.remove_closed_tab(0)

    def focus_tab(self, tab_nr):
        """
        Selects the playlist notebook tab tab_nr, and gives it the keyboard
        focus.
        """
        if tab_nr < self.get_n_pages():
            self.set_current_page(tab_nr)
            self.get_current_tab().focus()

    def select_next_tab(self):
        """
        Selects the previous playlist notebook tab, warping around if the
        first page is currently displayed.
        """
        tab_nr = self.get_current_page()
        tab_nr += 1
        tab_nr %= self.get_n_pages()
        self.set_current_page(tab_nr)

    def select_prev_tab(self):
        """
        Selects the next playlist notebook tab, warping around if the last
        page is currently displayed.
        """
        tab_nr = self.get_current_page()
        tab_nr -= 1
        tab_nr %= self.get_n_pages()
        self.set_current_page(tab_nr)

    def on_option_set(self, event, settings, option):
        """
        Updates appearance on setting change
        """
        if option == 'gui/show_tabbar':
            show_tabbar = settings.get_option(option, True)

            if not show_tabbar and self.get_n_pages() > 1:
                show_tabbar = True

            self.set_show_tabs(show_tabbar)

        if option == 'gui/tab_placement':
            tab_placement = settings.get_option(option, 'top')
            self.set_tab_pos(self.tab_placement_map[tab_placement])


class PlaylistContainer(Gtk.Box):
    """
    Contains two playlist notebooks that can contain playlists.
    Playlists can be moved between the two notebooks.

    TODO: Does it make sense to support more than two notebooks?
    I think with this implementation it does not -- we would need to
    move to a different UI design that allowed arbitrary placement
    of UI elements if that was the case.
    """

    def __init__(self, manager_name, player):
        Gtk.Box.__init__(self)

        self.notebooks: List[PlaylistNotebook] = []
        self.notebooks.append(
            PlaylistNotebook(manager_name, player, '<Primary><Shift>t')
        )
        self.notebooks.append(
            PlaylistNotebook(manager_name + '2', player, '<Primary><Alt>t')
        )

        self.notebooks[1].set_add_tab_on_empty(False)

        # add notebooks to self
        self.pack_start(self.notebooks[0], True, True, 0)

        # setup the paned window for separate views
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.pack2(self.notebooks[1], True, True)

        # setup queue page
        self.queuepage = QueuePage(self, player)
        self.queuetab = NotebookTab(None, self.queuepage)
        if len(player.queue) > 0:
            self.show_queue()

        # ensure default notebook always has a tab in it
        if self.notebooks[0].get_n_pages() == 0:
            self.notebooks[0].add_default_tab()

        # menu item
        item = menu.simple_menu_item(
            'move-tab',
            [],
            _('_Move to Other View'),
            None,
            lambda w, n, p, c: self._move_tab(p.tab),
            condition_fn=lambda n, p, c: True
            if p.tab.notebook in self.notebooks
            else False,
        )
        providers.register('playlist-tab-context-menu', item)
        providers.register('queue-tab-context', item)

        # connect events
        for notebook in self.notebooks:
            notebook.connect('page-reordered', self.on_page_reordered)
            notebook.connect_after(
                'page-removed', lambda *a: self._update_notebook_display()
            )

        self._update_notebook_display()

    def _move_tab(self, tab):
        if tab.notebook is self.notebooks[0]:
            src, dst = (0, 1)
        else:
            src, dst = (1, 0)

        # don't put this notebook in the 'recently closed tabs' list
        self.notebooks[src]._moving_tab = True
        self.notebooks[src].remove_tab(tab)
        self.notebooks[src]._moving_tab = False

        self.notebooks[dst].add_tab(tab, tab.page)

        # remember where the user moved the queue
        if tab.page is self.queuepage:
            settings.set_option('gui/queue_notebook_num', dst)

        self._update_notebook_display()

    def _update_notebook_display(self):
        pane_installed = self.paned.get_parent() is not None

        if self.notebooks[1].get_n_pages() != 0:
            if not pane_installed:
                parent = self.notebooks[0].get_parent()
                parent.remove(self.notebooks[0])

                self.paned.pack1(self.notebooks[0], True, True)
                self.pack_start(self.paned, True, True, 0)
        else:
            if pane_installed:
                parent = self.notebooks[0].get_parent()
                parent.remove(self.notebooks[0])

                self.remove(self.paned)
                self.pack_start(self.notebooks[0], True, True, 0)

        self.show_all()

    def create_new_playlist(self):
        """
        Create a new tab in the primary notebook containing a blank
        playlist. The tab will be automatically given a unique name.
        """
        return self.notebooks[0].create_new_playlist()

    def create_tab_from_playlist(self, pl):
        """
        Create a tab that will contain the passed-in playlist

        :param playlist: The playlist to create tab from
        :type playlist: :class:`xl.playlist.Playlist`
        """
        return self.notebooks[0].create_tab_from_playlist(pl)

    def get_current_notebook(self):
        """
        Returns the last focused notebook, or the
        primary notebook
        """
        if self.paned.get_parent() is not None:
            focus = self.paned.get_focus_child()
            if focus is not None:
                return focus
        return self.notebooks[0]

    def get_current_tab(self):
        """
        Returns the currently showing tab on the current notebook
        """
        notebook = self.get_current_notebook()
        return notebook.get_current_tab()

    def focus(self):
        """
        Gives keyboard focus to the currently selected tab
        """
        self.get_current_tab().focus()

    def on_page_reordered(self, notebook, child, page_number):
        if (
            self.queuepage.tab.notebook is notebook
            and notebook.page_num(self.queuepage) != 0
        ):
            notebook.reorder_child(self.queuepage, 0)

    def save_current_tabs(self):
        """
        Saves the open tabs
        """
        for notebook in self.notebooks:
            notebook.save_current_tabs()

    def show_queue(self, switch=True):
        """
        Shows the queue page in the last notebook that
        the queue was located.

        :param switch: If True, switch focus to the queue page
        """
        if self.queuepage.tab.notebook is None:
            # ensure the queue is restored in the last place the user had it
            n = settings.get_option('gui/queue_notebook_num', 0)
            self.notebooks[n].add_tab(self.queuetab, self.queuepage, position=0)
        if switch:
            # should always be 0, but doesn't hurt to be safe...
            qnotebook = self.queuepage.tab.notebook
            qnotebook.set_current_page(qnotebook.page_num(self.queuepage))

        self._update_notebook_display()

    def show_current_track(self):
        """
        Tries to find the currently playing track
        and selects it and its containing tab page
        """
        for notebook in self.notebooks:
            if notebook.show_current_track():
                break
