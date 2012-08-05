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

import collections
import glib
import gobject
import gtk
import logging
import os
import pango
import random
import re

from xl import (
    common,
    event,
    player,
    providers,
    settings,
    trax,
    xdg
)
from xl.common import MetadataList
from xl.nls import gettext as _
from xl.playlist import (
    Playlist,
    PlaylistManager,
    is_valid_playlist,
    import_playlist,
)
from xlgui import guiutil, icons
from xlgui.widgets import menu, menuitems, playlist_columns
from xlgui.widgets.notebook import NotebookPage

logger = logging.getLogger(__name__)

def default_get_playlist_func(parent, context):
    return player.QUEUE.current_playlist

class ModesMenuItem(menu.MenuItem):
    """
        A menu item having a submenu containing entries for shuffle modes.

        Defaults to adjusting the currently-playing playlist.
    """
    modetype = ''
    display_name = ""
    def __init__(self, name, after, get_playlist_func=default_get_playlist_func):
        menu.MenuItem.__init__(self, name, None, after)
        self.get_playlist_func = get_playlist_func

    def factory(self, menu, parent, context):
        item = gtk.ImageMenuItem(self.display_name)
        image = gtk.image_new_from_icon_name('media-playlist-'+self.modetype,
                size=gtk.ICON_SIZE_MENU)
        item.set_image(image)
        submenu = self.create_mode_submenu(item)
        item.set_submenu(submenu)
        pl = self.get_playlist_func(parent, context)
        item.set_sensitive(pl != None)
        return item

    def create_mode_submenu(self, parent_item):
        names = getattr(Playlist, "%s_modes"%self.modetype)
        displays = getattr(Playlist, "%s_mode_names"%self.modetype)
        items = []
        previous = None
        for name, display in zip(names, displays):
            after = [previous] if previous else []
            item = menu.radio_menu_item(name, after, display,
                    '%s_modes'%self.modetype, self.mode_is_selected,
                    self.on_mode_activated)
            items.append(item)
            if previous is None:
                items.append(menu.simple_separator("sep", [items[-1].name]))
            previous = items[-1].name
        m = menu.Menu(parent_item)
        for item in items:
            m.add_item(item)
        return m

    def mode_is_selected(self, name, parent, context):
        pl = self.get_playlist_func(parent, context)
        if pl is None:
            return False
        return getattr(pl, "%s_mode"%self.modetype) == name

    def on_mode_activated(self, widget, name, parent, context):
        pl = self.get_playlist_func(parent, context)
        if pl is None:
            return False
        setattr(pl, "%s_mode"%self.modetype, name)

class ShuffleModesMenuItem(ModesMenuItem):
    modetype = 'shuffle'
    display_name = _("Shuffle")

class RepeatModesMenuItem(ModesMenuItem):
    modetype = 'repeat'
    display_name = _("Repeat")

class DynamicModesMenuItem(ModesMenuItem):
    modetype = 'dynamic'
    display_name = _("Dynamic")

class RemoveCurrentMenuItem(menu.MenuItem):
    """
        Allows for removing the currently playing
        track from the current playlist
    """
    def __init__(self, after, get_playlist_func=default_get_playlist_func):
        menu.MenuItem.__init__(self, 'remove-current', None, after)
        self.get_playlist_func = get_playlist_func

    def factory(self, menu, parent, context):
        """
            Sets up the menu item
        """
        item = gtk.ImageMenuItem(_('Remove Current Track From Playlist'))
        item.set_image(gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU))
        item.connect('activate', self.on_activate)

        if player.PLAYER.is_stopped():
            item.set_sensitive(False)

        return item

    def on_activate(self, menuitem, playlist):
        """
            Removes the currently playing track from the current playlist
        """
        playlist = self.get_playlist_func()
        
        if playlist and playlist.current == player.PLAYER.current:
            del playlist[playlist.current_position]


# do this in a function to avoid polluting the global namespace
def __create_playlist_tab_context_menu():
    smi = menu.simple_menu_item
    sep = menu.simple_separator
    items = []
    items.append(smi('new-tab', [], _("New Playlist"), 'tab-new',
        lambda w, n, o, c: o.tab.notebook.create_new_playlist()))
    items.append(sep('new-tab-sep', ['new-tab']))
    items.append(smi('rename', ['new-tab-sep'], _("Rename"), 'gtk-edit',
        lambda w, n, o, c: o.tab.start_rename()))
    items.append(smi('clear', ['rename'], _("Clear"), 'gtk-clear',
        lambda w, n, o, c: o.playlist.clear()))
    items.append(sep('tab-close-sep', ['clear']))
    items.append(smi('tab-close', ['tab-close-sep'], _("Close"), 'gtk-close',
        lambda w, n, o, c: o.tab.close()))
    for item in items:
        providers.register('playlist-tab-context-menu', item)
__create_playlist_tab_context_menu()


class PlaylistContextMenu(menu.ProviderMenu):
    def __init__(self, page):
        """
            :param page: The :class:`PlaylistPage` this menu is
                associated with.
        """
        menu.ProviderMenu.__init__(self, 'playlist-context-menu', page)

    def get_context(self):
        context = common.LazyDict(self._parent)
        context['selected-items'] = lambda name, parent: parent.get_selected_items()
        context['selected-tracks'] = lambda name, parent: parent.get_selected_tracks()
        return context

class SPATMenuItem(menu.MenuItem):
    """
        Menu item allowing for toggling playback
        stop after the selected track (SPAT)
    """
    def __init__(self, name, after):
        menu.MenuItem.__init__(self, name, None, after)

    def factory(self, menu, parent, context):
        """
            Generates the menu item
        """
        display_name = _('Stop Playback After This Track')
        stock_id = gtk.STOCK_STOP

        if context['selected-items']:
            selection_position = context['selected-items'][0][0]

            if selection_position == parent.playlist.spat_position:
                display_name = _('Continue Playback After This Track')
                stock_id = gtk.STOCK_MEDIA_PLAY

        menuitem = gtk.ImageMenuItem(display_name)
        menuitem.set_image(gtk.image_new_from_stock(stock_id,
            gtk.ICON_SIZE_MENU))
        menuitem.connect('activate', self.on_menuitem_activate,
            parent, context)

        return menuitem

    def on_menuitem_activate(self, menuitem, parent, context):
        """
            Toggles the SPAT state
        """
        selection_position = context['selected-items'][0][0]

        if selection_position == parent.playlist.spat_position:
            parent.playlist.spat_position = -1
        else:
            parent.playlist.spat_position = selection_position

def __create_playlist_context_menu():
    smi = menu.simple_menu_item
    sep = menu.simple_separator
    items = []

    items.append(menuitems.EnqueueMenuItem('enqueue', []))

    items.append(SPATMenuItem('toggle-spat', [items[-1].name]))

    def rating_get_tracks_func(menuobj, parent, context):
        return [row[1] for row in context['selected-items']]
    items.append(menuitems.RatingMenuItem('rating', [items[-1].name]))

    # TODO: custom playlist item here
    items.append(sep('sep1', [items[-1].name]))

    def remove_tracks_cb(widget, name, playlistpage, context):
        tracks = context['selected-items']
        playlist = playlistpage.playlist
        # If it's all one block, just delete it in one chunk for
        # maximum speed.
        positions = [t[0] for t in tracks]
        if positions == range(positions[0], positions[0]+len(positions)):
            del playlist[positions[0]:positions[0]+len(positions)]
        else:
            for position, track in tracks[::-1]:
                del playlist[position]
    items.append(smi('remove', [items[-1].name], _('Remove'),
        gtk.STOCK_REMOVE, remove_tracks_cb))

    items.append(sep('sep2', [items[-1].name]))

    items.append(smi('properties', [items[-1].name], _('Properties'),
        gtk.STOCK_PROPERTIES, lambda w, n, o, c: o.show_properties_dialog()))

    for item in items:
        providers.register('playlist-context-menu', item)
__create_playlist_context_menu()


class PlaylistPage(NotebookPage):
    """
        Displays a playlist and associated controls.
    """
    menu_provider_name = 'playlist-tab-context-menu'
    def __init__(self, playlist, player):
        """
            :param playlist: The :class:`xl.playlist.Playlist` to display
                in this page.
            :param player: The :class:`xl.player._base.ExailePlayer` that 
                this page is associated with
            :param queue: 
        """
        NotebookPage.__init__(self)

        self.playlist = playlist
        self.icon = None

        uifile = xdg.get_data_path("ui", "playlist.ui")
        self.builder = gtk.Builder()
        self.builder.add_from_file(uifile)
        playlist_page = self.builder.get_object("playlist_page")

        for child in playlist_page.get_children():
            packing = playlist_page.query_child_packing(child)
            child.reparent(self)
            self.set_child_packing(child, *packing)

        self.shuffle_button = self.builder.get_object("shuffle_button")
        self.repeat_button = self.builder.get_object("repeat_button")
        self.dynamic_button = self.builder.get_object("dynamic_button")
        self.search_entry = guiutil.SearchEntry(
                self.builder.get_object("search_entry"))

        self.builder.connect_signals(self)

        self.playlist_window = self.builder.get_object("playlist_window")
        self.playlist_utilities_bar = self.builder.get_object(
            'playlist_utilities_bar')

        self.view = PlaylistView(playlist, player)
        self.playlist_window.add(self.view)
        self._filter_string = ""
        self._filter_matcher = None
        self.modelfilter = self.view.model.filter_new()
        self.modelfilter.set_visible_func(self.model_visible_func)
        self.view.set_model(self.modelfilter)

        event.add_callback(self.on_mode_changed,
            'playlist_shuffle_mode_changed', self.playlist,
            self.shuffle_button)
        event.add_callback(self.on_mode_changed,
            'playlist_repeat_mode_changed', self.playlist,
            self.repeat_button)
        event.add_callback(self.on_mode_changed,
            'playlist_dynamic_mode_changed', self.playlist,
            self.dynamic_button)
        event.add_callback(self.on_dynamic_playlists_provider_changed,
            'dynamic_playlists_provider_added')
        event.add_callback(self.on_dynamic_playlists_provider_changed,
            'dynamic_playlists_provider_removed')
        event.add_callback(self.on_option_set,
            'gui_option_set')

        self.on_mode_changed(None, None, self.playlist.shuffle_mode, self.shuffle_button)
        self.on_mode_changed(None, None, self.playlist.repeat_mode, self.repeat_button)
        self.on_mode_changed(None, None, self.playlist.dynamic_mode, self.dynamic_button)
        self.on_dynamic_playlists_provider_changed(None, None, None)
        self.on_option_set('gui_option_set', settings, 'gui/playlist_utilities_bar_visible')
        self.view.model.connect('row-changed', self.on_row_changed)

        self.show_all()

    ## NotebookPage API ##

    def get_name(self):
        return self.playlist.name

    def set_name(self, name):
        self.playlist.name = name

    def get_search_entry(self):
        return self.search_entry

    ## End NotebookPage ##

    def on_shuffle_button_press_event(self, widget, event):
        self.__show_toggle_menu(Playlist.shuffle_modes,
                Playlist.shuffle_mode_names, self.on_shuffle_mode_set,
                'shuffle_mode', widget, event)

    def on_repeat_button_press_event(self, widget, event):
        self.__show_toggle_menu(Playlist.repeat_modes,
                Playlist.repeat_mode_names, self.on_repeat_mode_set,
                'repeat_mode', widget, event)

    def on_dynamic_button_toggled(self, widget):
        if widget.get_active():
            self.playlist.dynamic_mode = self.playlist.dynamic_modes[1]
        else:
            self.playlist.dynamic_mode = self.playlist.dynamic_modes[0]

    def on_search_entry_activate(self, entry):
        self._filter_string = entry.get_text()
        if self._filter_string == "":
            self._filter_matcher = None
            self.modelfilter.refilter()
        else:
            self._filter_matcher = trax.TracksMatcher(self._filter_string,
                    case_sensitive=False,
                    keyword_tags=['artist', 'title', 'album'])
                    # FIXME: use currently-visible columns + base
                    # tags for filter
            logger.debug("Filtering playlist '%s' by '%s'."%(self.playlist.name, self._filter_string))
            self.modelfilter.refilter()
            logger.debug("Filtering playlist '%s' by '%s' completed."%(self.playlist.name, self._filter_string))


    def __show_toggle_menu(self, names, display_names, callback, attr,
            widget, event):
        """
            Display the menu on the shuffle/repeat toggle buttons

            :param names: The list of names of the menu entries
            :param display_names: The list of names to display on
                each menu entry.
            :param callback: The function to call when a menu item is
                activated. It will be passed the name of the activated item.
            :param attr: The attribute of self.playlist to look at to
                determine the currently-selected item.
            :param widget: The ToggleButton to display the menu on
            :param event: The gtk event that triggered the menu display
        """
        widget.set_active(True)
        menu = gtk.Menu()
        menu.connect('deactivate', self._mode_menu_set_toggle, widget, attr)
        prev = None
        mode = getattr(self.playlist, attr)
        for name, disp in zip(names, display_names):
            item = gtk.RadioMenuItem(prev, disp)
            if name == mode:
                item.set_active(True)
            item.connect('activate', callback, name)
            menu.append(item)
            if prev is None:
                menu.append(gtk.SeparatorMenuItem())
            prev = item
        menu.show_all()
        menu.popup(None, None, self._mode_menu_set_pos,
                event.button, event.time, widget)
        menu.reposition()

    def _mode_menu_set_pos(self, menu, button):
        """
            Nicely position the shuffle/repeat popup menu with the
            button's corner.
        """
        window_x, window_y = self.window.get_position()
        button_allocation = button.get_allocation()
        menu_allocation = menu.get_allocation()
        position = (
            window_x + button_allocation.x + 1,
            window_y + button_allocation.y - menu_allocation.height - 1
        )

        return (position[0], position[1], True)

    def _mode_menu_set_toggle(self, menu, button, name):
        mode = getattr(self.playlist, name)
        self.on_mode_changed(None, None, mode, button)

    def on_shuffle_mode_set(self, widget, mode):
        """
            Callback for the Shuffle mode menu
        """
        self.playlist.shuffle_mode = mode

    def on_repeat_mode_set(self, widget, mode):
        """
            Callback for the Repeat mode menu
        """
        self.playlist.repeat_mode = mode

    def on_mode_changed(self, evtype, playlist, mode, button):
        glib.idle_add(button.set_active, mode != 'disabled')

    def on_dynamic_playlists_provider_changed(self, evtype, manager, provider):
        """
            Updates the dynamic button on provider changes
        """
        providers_available = len(providers.get('dynamic_playlists')) > 0
        sensitive = False
        tooltip_text = _('Requires plugins providing dynamic playlists')

        if providers_available:
            sensitive = True
            tooltip_text = _('Dynamically add similar tracks to the playlist')

        glib.idle_add(self.dynamic_button.set_sensitive, sensitive)
        glib.idle_add(self.dynamic_button.set_tooltip_text, tooltip_text)

    def on_option_set(self, evtype, settings, option):
        """
            Handles option changes
        """
        if option == 'gui/playlist_utilities_bar_visible':
            visible = settings.get_option(option, True)
            glib.idle_add(self.playlist_utilities_bar.set_visible, visible)
            glib.idle_add(self.playlist_utilities_bar.set_sensitive, visible)
            glib.idle_add(self.playlist_utilities_bar.set_no_show_all, not visible)

    def on_row_changed(self, model, path, iter):
        """
            Sets the tab icon to reflect the playback status
        """
        if path[0] == self.playlist.current_position:
            pixbuf = model.get_value(iter, 1)
            if pixbuf == model.clear_pixbuf:
                pixbuf = None
            self.tab.set_icon(pixbuf)
            
        # there's a race condition on playback stop at the end of
        # a playlist (current_position gets set before this is called), 
        # so this sets the icon correctly. 
        elif self.playlist.current_position == -1:
            self.tab.set_icon(None)

    def model_visible_func(self, model, iter):
        if self._filter_matcher is not None:
            track = model.get_value(iter, 0)
            return self._filter_matcher.match(trax.SearchResultTrack(track))
        return True




class PlaylistView(guiutil.AutoScrollTreeView, providers.ProviderHandler):
    def __init__(self, playlist, player):
        guiutil.AutoScrollTreeView.__init__(self)
        providers.ProviderHandler.__init__(self, 'playlist-columns')

        self.playlist = playlist
        self.player = player
        self.model = PlaylistModel(playlist, playlist_columns.DEFAULT_COLUMNS, self.player)
        self.menu = PlaylistContextMenu(self)
        self.dragging = False
        self.button_pressed = False # used by columns to determine whether
                                    # a notify::width event was initiated
                                    # by the user.

        self.set_fixed_height_mode(True) # MASSIVE speedup - don't disable this!
        self.set_rules_hint(True)
        self.set_enable_search(True)
        self.selection = self.get_selection()
        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.set_model(self.model)
        self._setup_columns()
        self.columns_changed_id = self.connect("columns-changed",
                self.on_columns_changed)

        self.targets = [("exaile-index-list", gtk.TARGET_SAME_APP, 0),
                ("text/uri-list", 0, 0)]
        self.drag_source_set(gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT|
                gtk.gdk.ACTION_MOVE)

        event.add_callback(self.on_option_set, "gui_option_set")
        event.add_callback(self.on_playback_start, "playback_track_start", self.player)
        self.connect("cursor-changed", self.on_cursor_changed )
        self.connect("row-activated", self.on_row_activated)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("key-press-event", self.on_key_press_event)

        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-drop", self.on_drag_drop)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.connect("drag-end", self.on_drag_end)
        self.connect("drag-motion", self.on_drag_motion)

    def get_selected_tracks(self):
        """
            Returns a list of :class:`xl.trax.Track`
            which are currently selected in the playlist.
        """
        return [x[1] for x in self.get_selected_items()]

    def get_selected_paths(self):
        """
            Returns a list of pairs of treepaths
            which are currently selected in the playlist.
        """
        selection = self.get_selection()
        model, paths = selection.get_selected_rows()
        return paths

    def get_selected_items(self):
        """
            Returns a list of pairs of indices and :class:`xl.trax.Track`
            which are currently selected in the playlist.
        """
        paths = self.get_selected_paths()
        model = self.get_model()
        try:
            tracks = [(path[0], model.get_value(model.get_iter(path), 0)) for path in paths]
        except TypeError: #one of the paths was invalid
            return []
        return tracks

    def get_sort_column(self):
        for col in self.get_columns():
            if col.get_sort_indicator():
                return col
        return None

    def get_sort_by(self):
        sortcol = self.get_sort_column()
        if sortcol:
            reverse = sortcol.get_sort_order() == gtk.SORT_DESCENDING
            sort_by = [sortcol.name] + list(common.BASE_SORT_TAGS)
        else:
            reverse = False
            sort_by = list(common.BASE_SORT_TAGS)
        return (sort_by, reverse)

    def _setup_columns(self):
        columns = settings.get_option('gui/columns', playlist_columns.DEFAULT_COLUMNS)
        provider_names = [p.name for p in providers.get('playlist-columns')]
        columns = [name for name in columns if name in provider_names]

        if not columns:
            columns = playlist_columns.DEFAULT_COLUMNS

        # FIXME: this is kinda ick because of supporting both models
        self.model.columns = columns
        self.model = PlaylistModel(self.playlist, columns, self.player)
        self.set_model(self.model)

        for position, column in enumerate(columns):
            position += 2 # offset for pixbuf column
            playlist_column = providers.get_provider(
                'playlist-columns', column)(self, position, self.player)
            playlist_column.connect('clicked', self.on_column_clicked)
            self.append_column(playlist_column)
            header = playlist_column.get_widget()
            header.show()
            header.get_ancestor(gtk.Button).connect('button-press-event',
                self.on_header_button_press)

    def _refresh_columns(self):
        selection = self.get_selection()
        info = selection.get_selected_rows()
        # grab the first visible raw of the treeview
        firstpath = self.get_path_at_pos(4,4)
        topindex = None
        if firstpath:
            topindex = firstpath[0][0]

        self.disconnect(self.columns_changed_id)
        columns = self.get_columns()
        for col in columns:
            self.remove_column(col)

        self._setup_columns()
        self.columns_changed_id = self.connect("columns-changed",
                self.on_columns_changed)
        self.queue_draw()

        if firstpath:
            self.scroll_to_cell(topindex)
        if info:
            for path in info[1]:
                selection.select_path(path)

    def on_header_button_press(self, widget, event):
        if event.button == 3:
            m = menu.ProviderMenu('playlist-columns-menu', self)
            m.popup(None, None, None, event.button, event.time)
            return True

    def on_columns_changed(self, widget):
        columns = [c.name for c in self.get_columns()]
        if columns != settings.get_option('gui/columns', []):
            settings.set_option('gui/columns', columns)

    def on_column_clicked(self, column):
        order = None
        for col in self.get_columns():
            if col.name == column.name:
                order = column.get_sort_order()
                if order == gtk.SORT_ASCENDING:
                    order = gtk.SORT_DESCENDING
                else:
                    order = gtk.SORT_ASCENDING
                col.set_sort_indicator(True)
                col.set_sort_order(order)
            else:
                col.set_sort_indicator(False)
                col.set_sort_order(gtk.SORT_DESCENDING)
        reverse = order == gtk.SORT_DESCENDING
        self.playlist.sort([column.name] + list(common.BASE_SORT_TAGS), reverse=reverse)

    def on_option_set(self, typ, obj, data):
        if data == "gui/columns":
            glib.idle_add(self._refresh_columns, priority=glib.PRIORITY_DEFAULT)

    def on_playback_start(self, type, player, track):
        if player.queue.current_playlist == self.playlist and \
                player.current == self.playlist.current and \
                settings.get_option('gui/ensure_visible', True):
            glib.idle_add(self.scroll_to_current)

    def scroll_to_current(self):
        position = self.playlist.current_position
        if position >= 0:
            path = (position,)
            self.scroll_to_cell(path)
            self.set_cursor(path)
        
    def on_cursor_changed(self, widget):
        context = common.LazyDict(self)
        context['selected-items'] = lambda name, parent: parent.get_selected_items()
        context['selected-tracks'] = lambda name, parent: parent.get_selected_tracks()
        event.log_event( 'playlist_cursor_changed', self, context)
        

    def on_row_activated(self, *args):
        try:
            position, track = self.get_selected_items()[0]
        except IndexError:
            return

        self.playlist.set_current_position(position)
        self.player.queue.play(track=track)
        self.player.queue.set_current_playlist(self.playlist)

    def on_button_press(self, widget, event):
        self.button_pressed = True
        selection = self.get_selection()
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return not selection.count_selected_rows() <= 0
        elif event.button == 1:
            path = self.get_path_at_pos(int(event.x), int(event.y))
            if path:
                if selection.count_selected_rows() <= 1:
                    return False
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
        return False

    def on_button_release(self, widget, event):
        self.button_pressed = False
        if event.button != 1 or self.dragging:
            self.dragging = False
            return True

        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True

        selection = self.get_selection()
        selection.unselect_all()

        path = self.get_path_at_pos(int(event.x), int(event.y))
        if path:
            selection.select_path(path[0])

        return False

    def on_key_press_event(self, widget, event):
        if event.keyval == gtk.keysyms.Delete:
            indexes = [x[0] for x in self.get_selected_paths()]
            if indexes and indexes == range(indexes[0], indexes[0]+len(indexes)):
                del self.playlist[indexes[0]:indexes[0]+len(indexes)]
            else:
                for i in indexes[::-1]:
                    del self.playlist[i]

    ### DND handlers ###
    ## Source
    def on_drag_begin(self, widget, context):
        # TODO: set drag icon
        self.dragging = True

    def on_drag_data_get(self, widget, context, selection, info, etime):
        if selection.target == "exaile-index-list":
            positions = self.get_selected_paths()
            if positions:
                s = ",".join(str(i[0]) for i in positions)
                selection.set(selection.target, 8, s)
        elif selection.target == "text/uri-list":
            tracks = self.get_selected_tracks()
            uris = trax.util.get_uris_from_tracks(tracks)
            selection.set_uris(uris)

    def on_drag_data_delete(self, widget, context):
        self.stop_emission('drag-data-delete')

    def on_drag_end(self, widget, context):
        self.dragging = False

    ## Dest
    def on_drag_drop(self, widget, context, x, y, etime):
        return True

    def on_drag_data_received(self, widget, context, x, y, selection, info, etime):
        # Stop default handler from running
        self.stop_emission('drag-data-received')

        drop_info = self.get_dest_row_at_pos(x, y)

        if drop_info:
            path, position = drop_info
            insert_position = path[0]
            if position in (gtk.TREE_VIEW_DROP_AFTER, gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                insert_position += 1
        else:
            insert_position = -1

        tracks = []
        
        if selection.target == "exaile-index-list":
            positions = [int(x) for x in selection.data.split(",")]
            tracks = MetadataList()
            source_playlist_view = context.get_source_widget()
            playlist = self.playlist

            # Get the playlist of the 
            if source_playlist_view is not self:
                playlist = source_playlist_view.playlist

            # TODO: this can probably be made more-efficient
            for i in positions:
                tracks.extend(playlist[i:i+1])

            # Insert at specific position if possible
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks

                if source_playlist_view is self:
                    # Update position for tracks after the insert position
                    for i, position in enumerate(positions[:]):
                        if position >= insert_position:
                            position += len(tracks)
                            positions[i] = position
            else:
                # Otherwise just append the tracks
                self.playlist.extend(tracks)

            # Remove tracks from the source playlist if moved
            if context.action == gtk.gdk.ACTION_MOVE:
                for i in positions[::-1]:
                    del playlist[i]
        elif selection.target == "text/uri-list":
            uris = selection.get_uris()
            tracks = []
            for uri in uris:
                if is_valid_playlist(uri):
                    tracks.extend(import_playlist(uri))
                else:
                    tracks.extend(trax.get_tracks_from_uri(uri))
            sort_by, reverse = self.get_sort_by()
            tracks = trax.sort_tracks(sort_by, tracks, reverse=reverse)
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks
            else:
                self.playlist.extend(tracks)

        delete = context.action == gtk.gdk.ACTION_MOVE
        context.finish(True, delete, etime)

        scroll_when_appending_tracks = settings.get_option(
            'gui/scroll_when_appending_tracks', False)

        if scroll_when_appending_tracks and tracks:
            self.scroll_to_cell(self.playlist.index(tracks[-1]))

    def on_drag_motion(self, widget, context, x, y, etime):
        info = self.get_dest_row_at_pos(x, y)

        if not info:
            return False

        path, position = info

        if position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
            position = gtk.TREE_VIEW_DROP_BEFORE
        elif position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
            position = gtk.TREE_VIEW_DROP_AFTER

        self.set_drag_dest_row(path, position)

        action = gtk.gdk.ACTION_MOVE
        x, y, modifier = self.window.get_pointer()
        target = self.drag_dest_find_target(context, self.drag_dest_get_target_list())

        if modifier & gtk.gdk.CONTROL_MASK or target == 'text/uri-list':
            action = gtk.gdk.ACTION_COPY

        context.drag_status(action, etime)

        return True

    def show_properties_dialog(self):
        from xlgui import properties
        tracks = self.get_selected_tracks()
        current_position = 0
        if len(tracks) == 1:
            tracks = self.playlist[:]
            current_position = self.get_cursor()[0][0]

        if tracks:
            dialog = properties.TrackPropertiesDialog(None,
                    tracks, current_position)

    def on_provider_removed(self, provider):
        """
            Called when a column provider is removed
        """
        columns = settings.get_option('gui/columns')

        if provider.name in columns:
            columns.remove(provider.name)
            settings.set_option('gui/columns', columns)



class PlaylistModel(gtk.ListStore):

    def __init__(self, playlist, columns, player):
        gtk.ListStore.__init__(self, int) # real types are set later
        self.playlist = playlist
        self.columns = columns
        self.player = player

        self.coltypes = [object, gtk.gdk.Pixbuf] + [providers.get_provider('playlist-columns', c).datatype for c in columns]
        self.set_column_types(*self.coltypes)
        
        self._redraw_timer = None
        self._redraw_queue = []

        event.add_callback(self.on_tracks_added,
                "playlist_tracks_added", playlist)
        event.add_callback(self.on_tracks_removed,
                "playlist_tracks_removed", playlist)
        event.add_callback(self.on_current_position_changed,
                "playlist_current_position_changed", playlist)
        event.add_callback(self.on_spat_position_changed,
                "playlist_spat_position_changed", playlist)
        event.add_callback(self.on_playback_state_change,
                "playback_track_start", self.player)
        event.add_callback(self.on_playback_state_change,
                "playback_track_end", self.player)
        event.add_callback(self.on_playback_state_change,
                "playback_player_pause", self.player)
        event.add_callback(self.on_playback_state_change,
                "playback_player_resume", self.player)
        event.add_callback(self.on_track_tags_changed,
                "track_tags_changed")

        self.play_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(gtk.STOCK_MEDIA_PLAY))
        self.pause_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(gtk.STOCK_MEDIA_PAUSE))
        self.stop_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(gtk.STOCK_STOP))
        stop_overlay_pixbuf = self.stop_pixbuf.scale_simple(
                dest_width=self.stop_pixbuf.get_width() / 2,
                dest_height=self.stop_pixbuf.get_height() / 2,
                interp_type=gtk.gdk.INTERP_BILINEAR)
        stop_overlay_pixbuf = stop_overlay_pixbuf.move(
                offset_x=stop_overlay_pixbuf.get_width(),
                offset_y=stop_overlay_pixbuf.get_height(),
                resize=True)
        self.play_stop_pixbuf = self.play_pixbuf & stop_overlay_pixbuf
        self.pause_stop_pixbuf = self.pause_pixbuf & stop_overlay_pixbuf
        self.clear_pixbuf = self.play_pixbuf.copy()
        self.clear_pixbuf.fill(0x00000000)

        self.on_tracks_added(None, self.playlist, enumerate(self.playlist)) # populate the list

    def track_to_row_data(self, track, position):
        return [track, self.icon_for_row(position)] + [providers.get_provider('playlist-columns', name).formatter.format(track) for name in self.columns]

    def icon_for_row(self, row):
        # TODO: we really need some sort of global way to say "is this playlist/pos the current one?
        if self.playlist.current_position == row and \
                self.playlist[row] == self.player.current and \
                self.playlist == self.player.queue.current_playlist:
            state = self.player.get_state()
            spat = self.playlist.spat_position == row
            if state == 'playing':
                if spat:
                    return self.play_stop_pixbuf
                else:
                    return self.play_pixbuf
            elif state == 'paused':
                if spat:
                    return self.pause_stop_pixbuf
                else:
                    return self.pause_pixbuf
        if self.playlist.spat_position == row:
            return self.stop_pixbuf
        return self.clear_pixbuf

    def update_icon(self, position):
        iter = self.iter_nth_child(None, position)
        if iter is not None:
            self.set(iter, 1, self.icon_for_row(position))

    ### Event callbacks to keep the model in sync with the playlist ###

    def on_tracks_added(self, event_type, playlist, tracks):
        for position, track in tracks:
            self.insert(position, self.track_to_row_data(track, position))

    def on_tracks_removed(self, event_type, playlist, tracks):
        tracks.reverse()
        for position, track in tracks:
            self.remove(self.iter_nth_child(None, position))

    def on_current_position_changed(self, event_type, playlist, positions):
        for position in positions:
            if position < 0:
                continue
            glib.idle_add(self.update_icon, position)

    def on_spat_position_changed(self, event_type, playlist, positions):
        spat_position = max(positions)
        for position in xrange(spat_position, len(self)):
            glib.idle_add(self.update_icon, position)

    def on_playback_state_change(self, event_type, player_obj, track):
        position = self.playlist.current_position
        if position < 0 or position >= len(self):
            return
        glib.idle_add(self.update_icon, position)

    def on_track_tags_changed(self, type, track, tag):
        if not track or not \
            settings.get_option('gui/sync_on_tag_change', True) or not\
            tag in self.columns:
            return
            
        if self._redraw_timer:
            glib.source_remove(self._redraw_timer)
        self._redraw_queue.append( track )
        self._redraw_timer = glib.timeout_add(100, self._on_track_tags_changed)
            
    def _on_track_tags_changed(self):
        tracks = {}
        for track in self._redraw_queue:
            tracks[track.get_loc_for_io()] = track
        self._redraw_queue = []
           
        for row in self:
            track = tracks.get( row[0].get_loc_for_io() )
            if track is not None:
                track_data = [providers.get_provider('playlist-columns', name).formatter.format(track) for name in self.columns]
                for i in range(len(track_data)):
                    row[2+i] = track_data[i]
                
        
        
    
