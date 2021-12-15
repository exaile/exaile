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
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

import logging
import sys

from xl.nls import gettext as _
from xl.playlist import Playlist, is_valid_playlist, import_playlist
from xl import common, event, main, player, providers, settings, trax, xdg

from xlgui.widgets.common import AutoScrollTreeView
from xlgui.widgets.notebook import NotebookPage
from xlgui.widgets import dialogs, menu, menuitems, playlist_columns
from xlgui import guiutil, icons

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
        item = Gtk.ImageMenuItem.new_with_mnemonic(self.display_name)
        image = Gtk.Image.new_from_icon_name(
            'media-playlist-' + self.modetype, size=Gtk.IconSize.MENU
        )
        item.set_image(image)
        submenu = self.create_mode_submenu(item)
        item.set_submenu(submenu)
        pl = self.get_playlist_func(parent, context)
        item.set_sensitive(pl is not None)
        return item

    def create_mode_submenu(self, parent_item):
        names = getattr(Playlist, "%s_modes" % self.modetype)
        displays = getattr(Playlist, "%s_mode_names" % self.modetype)
        items = []
        previous = None
        for name, display in zip(names, displays):
            after = [previous] if previous else []
            item = menu.radio_menu_item(
                name,
                after,
                display,
                '%s_modes' % self.modetype,
                self.mode_is_selected,
                self.on_mode_activated,
            )
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
        return getattr(pl, "%s_mode" % self.modetype) == name

    def on_mode_activated(self, widget, name, parent, context):
        pl = self.get_playlist_func(parent, context)
        if pl is None:
            return False
        setattr(pl, "%s_mode" % self.modetype, name)


class ShuffleModesMenuItem(ModesMenuItem):
    modetype = 'shuffle'
    display_name = _("S_huffle")


class RepeatModesMenuItem(ModesMenuItem):
    modetype = 'repeat'
    display_name = _("R_epeat")


class DynamicModesMenuItem(ModesMenuItem):
    modetype = 'dynamic'
    display_name = _("_Dynamic")


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
        item = Gtk.ImageMenuItem.new_with_mnemonic(
            _('Remove _Current Track From Playlist')
        )
        item.set_image(Gtk.Image.new_from_icon_name('list-remove', Gtk.IconSize.MENU))
        item.connect('activate', self.on_activate, parent, context)

        if player.PLAYER.is_stopped():
            item.set_sensitive(False)

        return item

    def on_activate(self, menuitem, parent, context):
        """
        Removes the currently playing track from the current playlist
        """
        playlist = self.get_playlist_func(parent, context)

        if playlist and playlist.current == player.PLAYER.current:
            del playlist[playlist.current_position]


class RandomizeMenuItem(menu.MenuItem):
    """
    A menu item which randomizes the full
    playlist or the current selection
    """

    def __init__(self, after):
        menu.MenuItem.__init__(self, 'randomize', None, after)

    def factory(self, menu, parent, context):
        """
        Sets up the menu item
        """
        label = _('R_andomize Playlist')

        if not context['selection-empty']:
            label = _('R_andomize Selection')

        item = Gtk.MenuItem.new_with_mnemonic(label)
        item.connect('activate', self.on_activate, parent, context)

        return item

    def on_activate(self, menuitem, parent, context):
        """
        Randomizes the playlist or the selection
        """
        positions = [path[0] for path in context['selected-paths']]
        # Randomize the full playlist if only one track was selected
        positions = positions if len(positions) > 1 else []

        # If you don't unselect before randomizing, a large number of selected will
        # kill performance
        parent.get_selection().unselect_all()
        with parent.handler_block(parent._cursor_changed):
            context['playlist'].randomize(positions)


# do this in a function to avoid polluting the global namespace
def __create_playlist_tab_context_menu():
    smi = menu.simple_menu_item
    sep = menu.simple_separator
    items = []
    items.append(
        smi(
            'new-tab',
            [],
            _("_New Playlist"),
            'tab-new',
            lambda w, n, o, c: o.tab.notebook.create_new_playlist(),
        )
    )
    items.append(sep('new-tab-sep', ['new-tab']))

    items.append(
        smi(
            'save',
            ['new-tab-sep'],
            _("_Save"),
            'document-save',
            callback=lambda w, n, p, c: p.on_save(),
            condition_fn=lambda n, p, c: (
                p.can_save()
                and main.exaile().playlists.has_playlist_name(p.playlist.name)
            ),
        )
    )
    items.append(
        smi(
            'saveas',
            ['save'],
            _("Save _As"),
            'document-save-as',
            callback=lambda w, n, p, c: p.on_saveas(),
            condition_fn=lambda n, p, c: p.can_saveas(),
        )
    )
    items.append(
        smi(
            'rename',
            ['saveas'],
            _("_Rename"),
            None,
            callback=lambda w, n, p, c: p.tab.start_rename(),
            condition_fn=lambda n, p, c: p.tab.can_rename(),
        )
    )
    items.append(
        smi(
            'clear',
            ['rename'],
            _("_Clear"),
            'edit-clear-all',
            lambda w, n, o, c: o.playlist.clear(),
        )
    )
    items.append(sep('tab-close-sep', ['clear']))

    def _get_pl_func(o, c):
        return o.playlist

    items.append(
        menuitems.ExportPlaylistMenuItem('export', ['tab-close-sep'], _get_pl_func)
    )
    items.append(
        menuitems.ExportPlaylistFilesMenuItem('export-files', ['export'], _get_pl_func)
    )
    items.append(sep('tab-export-sep', ['export']))
    items.append(
        smi(
            'tab-close',
            ['tab-export-sep'],
            _("Close _Tab"),
            'window-close',
            lambda w, n, o, c: o.tab.close(),
        )
    )
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
        self.attach_to_widget(page, None)

    def get_context(self):
        context = common.LazyDict(self._parent)
        context['playlist'] = lambda name, parent: parent.playlist
        context['selection-empty'] = (
            lambda name, parent: parent.get_selection_count() == 0
        )
        context['selected-paths'] = lambda name, parent: parent.get_selected_paths()
        context['selected-items'] = lambda name, parent: parent.get_selected_items()
        context['selected-tracks'] = lambda name, parent: parent.get_selected_tracks()
        context['selection-count'] = lambda name, parent: parent.get_selection_count()
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
        display_name = _('_Stop Playback After This Track')
        icon_name = 'media-playback-stop'

        if context['selected-items']:
            selection_position = context['selected-items'][0][0]

            if selection_position == parent.playlist.spat_position:
                display_name = _('_Continue Playback After This Track')
                icon_name = 'media-playback-start'

        menuitem = Gtk.ImageMenuItem.new_with_mnemonic(display_name)
        menuitem.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU))
        menuitem.connect('activate', self.on_menuitem_activate, parent, context)

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
        if positions == list(range(positions[0], positions[0] + len(positions))):
            del playlist[positions[0] : positions[0] + len(positions)]
        else:
            for position, track in tracks[::-1]:
                del playlist[position]

    items.append(
        smi(
            'remove',
            [items[-1].name],
            _("_Remove from Playlist"),
            'list-remove',
            remove_tracks_cb,
        )
    )

    items.append(RandomizeMenuItem([items[-1].name]))

    def playlist_menu_condition(name, parent, context):
        """
        Returns True if the containing notebook's tab bar is hidden
        """
        scrolledwindow = parent.get_parent()
        page = scrolledwindow.get_parent()
        return not page.tab.notebook.get_show_tabs()

    items.append(
        smi(
            'playlist-menu',
            [items[-1].name],
            _('Playlist'),
            submenu=menu.ProviderMenu('playlist-tab-context-menu', None),
            condition_fn=playlist_menu_condition,
        )
    )

    items.append(sep('sep2', [items[-1].name]))

    items.append(
        smi(
            'properties',
            [items[-1].name],
            _("_Track Properties"),
            'document-properties',
            lambda w, n, o, c: o.show_properties_dialog(),
        )
    )

    for item in items:
        providers.register('playlist-context-menu', item)


__create_playlist_context_menu()


class PlaylistPageBase(NotebookPage):
    """
    Base class for playlist pages. Subclasses can indicate that
    they support the following operations:

    save:
        - Define a function called 'on_save'

    save as:
        - Define a function called 'on_saveas'
    """

    menu_provider_name = 'playlist-tab-context-menu'

    def can_save(self):
        return hasattr(self, 'on_save')

    def can_saveas(self):
        return hasattr(self, 'on_saveas')


class PlaylistPage(PlaylistPageBase):
    """
    Displays a playlist and associated controls.
    """

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

        self.loading = None
        self.loading_timer = None

        self.play_pixbuf = icons.MANAGER.pixbuf_from_icon_name(
            'media-playback-start', size=Gtk.IconSize.MENU
        )
        self.pause_pixbuf = icons.MANAGER.pixbuf_from_icon_name(
            'media-playback-pause', size=Gtk.IconSize.MENU
        )

        uifile = xdg.get_data_path("ui", "playlist.ui")
        self.builder = Gtk.Builder()
        self.builder.add_from_file(uifile)
        playlist_page = self.builder.get_object("playlist_page")

        for child in playlist_page.get_children():
            packing = playlist_page.query_child_packing(child)
            playlist_page.remove(child)
            self.add(child)
            self.set_child_packing(child, *packing)

        self.shuffle_button = self.builder.get_object("shuffle_button")
        self.repeat_button = self.builder.get_object("repeat_button")
        self.dynamic_button = self.builder.get_object("dynamic_button")
        self.search_entry = guiutil.SearchEntry(self.builder.get_object("search_entry"))

        self.builder.connect_signals(self)

        self.playlist_window = self.builder.get_object("playlist_window")
        self.playlist_utilities_bar = self.builder.get_object('playlist_utilities_bar')

        self.view = PlaylistView(playlist, player)
        self.view.set_search_entry(self.search_entry.entry)
        self.view.connect(
            'start-interactive-search', lambda *a: self.search_entry.entry.grab_focus()
        )

        self.playlist_window.add(self.view)

        event.add_ui_callback(
            self.on_mode_changed,
            'playlist_shuffle_mode_changed',
            self.playlist,
            self.shuffle_button,
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_mode_changed,
            'playlist_repeat_mode_changed',
            self.playlist,
            self.repeat_button,
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_mode_changed,
            'playlist_dynamic_mode_changed',
            self.playlist,
            self.dynamic_button,
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_dynamic_playlists_provider_changed,
            'dynamic_playlists_provider_added',
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_dynamic_playlists_provider_changed,
            'dynamic_playlists_provider_removed',
            destroy_with=self,
        )
        event.add_ui_callback(self.on_option_set, 'gui_option_set', destroy_with=self)

        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_track_start",
            player,
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_track_end",
            player,
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_player_pause",
            player,
            destroy_with=self,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_player_resume",
            player,
            destroy_with=self,
        )

        self.on_mode_changed(
            None, None, self.playlist.shuffle_mode, self.shuffle_button
        )
        self.on_mode_changed(None, None, self.playlist.repeat_mode, self.repeat_button)
        self.on_mode_changed(
            None, None, self.playlist.dynamic_mode, self.dynamic_button
        )
        self.on_dynamic_playlists_provider_changed(None, None, None)
        self.on_option_set(
            'gui_option_set', settings, 'gui/playlist_utilities_bar_visible'
        )
        self.view.connect('button-press-event', self.on_view_button_press_event)
        self.view.model.connect('data-loading', self.on_data_loading)

        if self.view.model.data_loading:
            self.on_data_loading(None, True)

        self.show_all()

    ## NotebookPage API ##

    def focus(self):
        self.view.grab_focus()

    def get_page_name(self):
        return self.playlist.name

    def set_page_name(self, name):
        self.playlist.name = name
        self.name_changed()

    def get_search_entry(self):
        return self.search_entry

    ## End NotebookPage ##

    ## PlaylistPageBase API ##

    # TODO: These two probably shouldn't reach back to main..
    def on_save(self):
        main.exaile().playlists.save_playlist(self.playlist, overwrite=True)

    def on_saveas(self):
        exaile = main.exaile()
        playlists = exaile.playlists
        name = dialogs.ask_for_playlist_name(
            exaile.gui.main.window, playlists, self.playlist.name
        )
        if name is not None:
            self.set_page_name(name)
            playlists.save_playlist(self.playlist)

    ## End PlaylistPageBase API ##

    def on_shuffle_button_press_event(self, widget, event):
        self.__show_toggle_menu(
            Playlist.shuffle_modes,
            Playlist.shuffle_mode_names,
            self.on_shuffle_mode_set,
            'shuffle_mode',
            widget,
            event,
        )

    def on_shuffle_button_popup_menu(self, widget):
        self.__show_toggle_menu(
            Playlist.shuffle_modes,
            Playlist.shuffle_mode_names,
            self.on_shuffle_mode_set,
            'shuffle_mode',
            widget,
            None,
        )
        return True

    def on_repeat_button_press_event(self, widget, event):
        self.__show_toggle_menu(
            Playlist.repeat_modes,
            Playlist.repeat_mode_names,
            self.on_repeat_mode_set,
            'repeat_mode',
            widget,
            event,
        )

    def on_repeat_button_popup_menu(self, widget):
        self.__show_toggle_menu(
            Playlist.repeat_modes,
            Playlist.repeat_mode_names,
            self.on_repeat_mode_set,
            'repeat_mode',
            widget,
            None,
        )
        return True

    def on_dynamic_button_toggled(self, widget):
        if widget.get_active():
            self.playlist.dynamic_mode = self.playlist.dynamic_modes[1]
        else:
            self.playlist.dynamic_mode = self.playlist.dynamic_modes[0]

    def on_search_entry_activate(self, entry):
        filter_string = entry.get_text()
        self.view.filter_tracks(filter_string or None)

    def __show_toggle_menu(self, names, display_names, callback, attr, widget, event):
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
        menu = Gtk.Menu()
        menu.connect('deactivate', self._mode_menu_set_toggle, widget, attr)
        prev = None
        mode = getattr(self.playlist, attr)
        for name, disp in zip(names, display_names):
            group = None if prev is None else prev.get_group()
            item = Gtk.RadioMenuItem.new_with_mnemonic(group, disp)
            if name == mode:
                item.set_active(True)
            item.connect('activate', callback, name)
            menu.append(item)
            if prev is None:
                menu.append(Gtk.SeparatorMenuItem())
            prev = item
        menu.attach_to_widget(widget)
        menu.show_all()
        if event is not None:
            menu.popup(
                None, None, guiutil.position_menu, widget, event.button, event.time
            )
        else:
            menu.popup(None, None, guiutil.position_menu, widget, 0, 0)
        menu.reposition()

    def _mode_menu_set_toggle(self, menu, button, name):
        mode = getattr(self.playlist, name)
        self.on_mode_changed(None, None, mode, button)

    def on_shuffle_mode_set(self, widget, mode):
        """
        Callback for the Shuffle mode menu
        """
        if widget.get_active():
            self.playlist.shuffle_mode = mode

    def on_repeat_mode_set(self, widget, mode):
        """
        Callback for the Repeat mode menu
        """
        if widget.get_active():
            self.playlist.repeat_mode = mode

    def on_mode_changed(self, evtype, playlist, mode, button):
        button.set_active(mode != 'disabled')

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

        self.dynamic_button.set_sensitive(sensitive)
        self.dynamic_button.set_tooltip_text(tooltip_text)

    def on_option_set(self, evtype, settings, option):
        """
        Handles option changes
        """
        if option == 'gui/playlist_utilities_bar_visible':
            visible = settings.get_option(option, True)
            self.playlist_utilities_bar.set_visible(visible)
            self.playlist_utilities_bar.set_sensitive(visible)
            self.playlist_utilities_bar.set_no_show_all(not visible)

    def on_playback_state_change(self, typ, player, track):
        """
        Sets the tab icon to reflect the playback status
        """
        if player.queue.current_playlist != self.playlist:
            self.tab.set_icon(None)
        elif typ in ('playback_player_end', 'playback_track_end'):
            self.tab.set_icon(None)
        elif typ in ('playback_track_start', 'playback_player_resume'):
            self.tab.set_icon(self.play_pixbuf)
        elif typ == 'playback_player_pause':
            self.tab.set_icon(self.pause_pixbuf)

    def on_data_loading(self, model, loading):
        '''Called when tracks are being loaded into the model'''
        if loading:
            if self.loading is None and self.loading_timer is None:
                self.view.set_model(None)
                self.loading_timer = GLib.timeout_add(500, self.on_data_loading_timer)
        else:
            if self.loading_timer is not None:
                GLib.source_remove(self.loading_timer)
                self.loading_timer = None

            self.view.set_model(self.view.modelfilter)

            if self.loading is not None:
                guiutil.gtk_widget_replace(self.loading, self.playlist_window)
                self.loading.destroy()
                self.loading = None

    def on_data_loading_timer(self):

        if self.loading_timer is None:
            return

        self.loading_timer = None

        grid = Gtk.Grid()
        sp = Gtk.Spinner()
        sp.start()
        lbl = Gtk.Label.new(_('Loading'))

        grid.attach(sp, 0, 0, 1, 1)
        grid.attach(lbl, 1, 0, 1, 1)

        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)

        self.loading = grid

        guiutil.gtk_widget_replace(self.playlist_window, self.loading)
        self.loading.show_all()

    def on_view_button_press_event(self, view, e):
        """
        Displays the tab context menu upon
        clicks in the contained view
        """
        path = view.get_path_at_pos(int(e.x), int(e.y))
        # We only need the tree path if present
        path = path[0] if path else None

        if (
            not path
            and e.type == Gdk.EventType.BUTTON_PRESS
            and e.triggers_context_menu()
        ):
            self.tab_menu.popup(None, None, None, None, e.button, e.time)


class PlaylistView(AutoScrollTreeView, providers.ProviderHandler):
    __gsignals__ = {}

    def __init__(self, playlist, player):
        AutoScrollTreeView.__init__(self)
        providers.ProviderHandler.__init__(self, 'playlist-columns')

        self.playlist = playlist
        self.player = player

        self._current_vertical_scroll = 0
        self._insert_row = -1
        self._insert_count = 0

        self.menu = PlaylistContextMenu(self)
        self.header_menu = menu.ProviderMenu('playlist-columns-menu', self)
        self.header_menu.attach_to_widget(self)

        self.dragging = False
        self.pending_event = None

        self.pending_edit_id = None  # Timeout to ensure a double-click didn't occur
        self.pending_edit_data = None  # (path, col) or None
        self.pending_edit_ok = False  # Set to True by release or timeout

        self._insert_focusing = False

        self._hack_is_osx = sys.platform == 'darwin'
        self._hack_osx_control_mask = False

        # Set to true if you only want things to be copied here, not moved
        self.dragdrop_copyonly = False

        self.set_fixed_height_mode(True)  # MASSIVE speedup - don't disable this!
        self.set_enable_search(True)
        self.selection = self.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        self._filter_matcher = None

        self._sort_columns = list(common.BASE_SORT_TAGS)  # Column sort order

        self._setup_models()
        self._setup_columns()
        self.columns_changed_id = self.connect(
            "columns-changed", self.on_columns_changed
        )

        self.targets = [
            Gtk.TargetEntry.new("exaile-index-list", Gtk.TargetFlags.SAME_APP, 0),
            Gtk.TargetEntry.new("text/uri-list", 0, 0),
        ]
        self.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            self.targets,
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE,
        )
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            self.targets,
            Gdk.DragAction.COPY | Gdk.DragAction.DEFAULT | Gdk.DragAction.MOVE,
        )

        event.add_ui_callback(self.on_option_set, "gui_option_set", destroy_with=self)
        event.add_ui_callback(
            self.on_playback_start,
            "playback_track_start",
            self.player,
            destroy_with=self,
        )
        self._cursor_changed = self.connect("cursor-changed", self.on_cursor_changed)
        self.connect("row-activated", self.on_row_activated)
        self.connect("key-press-event", self.on_key_press_event)

        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-drop", self.on_drag_drop)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.connect("drag-end", self.on_drag_end)
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("size-allocate", self.on_size_allocate)

    def do_destroy(self):
        # if this isn't disconnected, then the columns are emptied out and
        # the user's settings are overwritten with an empty list
        self.disconnect(self.columns_changed_id)
        AutoScrollTreeView.do_destroy(self)

    def _refilter(self):
        with guiutil.without_model(self):
            self.modelfilter.refilter()

    def filter_tracks(self, filter_string):
        """
        Only show tracks that match the filter. If filter is None, then
        clear any existing filters.

        The filter will search any currently enabled columns AND the
        default columns.
        """

        if filter_string is None:
            self._filter_matcher = None
            self._refilter()
        else:
            # Merge default columns and currently enabled columns
            keyword_tags = set(
                playlist_columns.DEFAULT_COLUMNS
                + [c.name for c in self.get_columns()[1:]]
            )
            self._filter_matcher = trax.TracksMatcher(
                filter_string, case_sensitive=False, keyword_tags=keyword_tags
            )
            logger.debug(
                "Filtering playlist %r by %r.", self.playlist.name, filter_string
            )
            self._refilter()
            logger.debug(
                "Filtering playlist %r by %r completed.",
                self.playlist.name,
                filter_string,
            )

    def get_selection_count(self):
        """
        Returns the number of items currently selected in the
        playlist. Prefer this to len(get_selected_tracks()) et al
        if you will discard the actual track list
        """
        return self.get_selection().count_selected_rows()

    def get_selected_tracks(self):
        """
        Returns a list of :class:`xl.trax.Track`
        which are currently selected in the playlist.
        """
        return [x[1] for x in self.get_selected_items()]

    def get_selected_paths(self):
        """
        Returns a list of pairs of treepaths which are currently
        selected in the playlist.

        The treepaths are returned for the base model, so they are
        indices that can be used with the playlist currently
        associated with this view.
        """
        selection = self.get_selection()
        model, paths = selection.get_selected_rows()

        if isinstance(model, Gtk.TreeModelFilter):
            paths = [model.convert_path_to_child_path(path) for path in paths]

        return paths

    def get_selected_items(self):
        """
        Returns a list of pairs of indices and :class:`xl.trax.Track`
        which are currently selected in the playlist.

        The indices can be used with the playlist currently associated
        with this view.
        """
        selection = self.get_selection()
        model, paths = selection.get_selected_rows()
        try:
            if isinstance(model, Gtk.TreeModelFilter):
                tracks = [
                    (
                        model.convert_path_to_child_path(path)[0],
                        model.get_value(model.get_iter(path), 0),
                    )
                    for path in paths
                ]
            else:
                tracks = [
                    (path[0], model.get_value(model.get_iter(path), 0))
                    for path in paths
                ]
        except TypeError:  # one of the paths was invalid
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
            reverse = sortcol.get_sort_order() == Gtk.SortType.DESCENDING
        else:
            reverse = False
        return (self._sort_columns, reverse)

    def play_track_at(self, position, track):
        """
        When called, this will begin playback of a track at a given
        position in the internal playlist
        """
        self._play_track_at(position, track)

    def _play_track_at(
        self, position, track, on_activated=False, restart_if_playing=False
    ):
        '''Internal API'''
        if not settings.get_option('playlist/enqueue_by_default', False) or (
            self.playlist is self.player.queue and on_activated
        ):
            # If track is already playing, then:
            # a) if restart_if_playing flag is set, restart the track
            # b) otherwise, pause/resume it instead of starting over
            if (
                on_activated
                and not self.player.is_stopped()
                and self.player.queue.current_playlist is self.playlist
                and self.playlist.get_current_position() == position
                and not (restart_if_playing and self.player.is_playing())
            ):
                self.player.toggle_pause()

            elif self.player.queue.is_play_enabled():
                self.playlist.set_current_position(position)
                self.player.queue.set_current_playlist(self.playlist)
                self.player.queue.play(track=track)
        elif self.playlist is not self.player.queue:
            self.player.queue.append(track)

    def _setup_columns(self):
        columns = settings.get_option('gui/columns', playlist_columns.DEFAULT_COLUMNS)
        provider_names = [p.name for p in providers.get('playlist-columns')]
        columns = [name for name in columns if name in provider_names]

        if not columns:
            columns = playlist_columns.DEFAULT_COLUMNS

        self.model._set_columns(columns)

        font, ratio = self._compute_font()

        # create a fixed column for the playlist icon
        self._setup_fixed_column(ratio)

        for column in columns:
            playlist_column = providers.get_provider('playlist-columns', column)(
                self, self.player, font, ratio
            )
            playlist_column.connect('clicked', self.on_column_clicked)

            if isinstance(playlist_column.cellrenderer, Gtk.CellRendererText):
                playlist_column.set_attributes(
                    playlist_column.cellrenderer,
                    sensitive=PlaylistModel.COL_SENSITIVE,
                    weight=PlaylistModel.COL_WEIGHT,
                )
            else:
                playlist_column.set_attributes(
                    playlist_column.cellrenderer, sensitive=PlaylistModel.COL_SENSITIVE
                )

            self.append_column(playlist_column)
            header = playlist_column.get_widget()
            header.show()
            header.get_ancestor(Gtk.Button).connect(
                'button-press-event', self.on_header_button_press
            )

            header.get_ancestor(Gtk.Button).connect(
                'key-press-event', self.on_header_key_press_event
            )

    def _compute_font(self):

        font = settings.get_option('gui/playlist_font', None)
        if font is not None:
            font = Pango.FontDescription(font)

        default_font = Gtk.Widget.get_default_style().font_desc
        if font is None:
            font = default_font

        def_font_sz = default_font.get_size()

        # how much has the font deviated from normal?
        ratio = font.get_size() / def_font_sz

        # small fonts can be problematic..
        # -> TODO: perhaps default widths could be specified
        #          in character widths instead? then we could
        #          calculate it instead of using arbitrary widths
        if ratio < 1:
            ratio = ratio * 1.25

        return font, ratio

    def _setup_fixed_column(self, ratio):
        sz = Gtk.icon_size_lookup(Gtk.IconSize.BUTTON)[1]
        sz = max(int(sz * ratio), 1)

        cell = Gtk.CellRendererPixbuf()
        cell.set_property('xalign', 0.0)

        col = Gtk.TreeViewColumn('')
        col.pack_start(cell, False)
        col.set_max_width(sz)
        col.set_attributes(cell, pixbuf=PlaylistModel.COL_PIXBUF)
        col.set_resizable(False)
        col.set_reorderable(False)
        col.set_clickable(False)
        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(col)

    def _on_resize_columns(self):
        for col in self.cols:
            col._setup_sizing()
        pass

    def _refresh_columns(self):
        selection = self.get_selection()
        if not selection:  # The widget has been destroyed
            return

        with self.handler_block(self.columns_changed_id):
            columns = self.get_columns()
            for col in columns:
                self.remove_column(col)
                col.destroyed = True

            self._setup_columns()

        self.queue_draw()

    def _setup_models(self):
        self.model = PlaylistModel(self.playlist, [], self.player, self)
        self.model.connect('row-inserted', self.on_row_inserted)

        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(self._modelfilter_visible_func)
        self.set_model(self.modelfilter)

    def _modelfilter_visible_func(self, model, iter, data):
        if self._filter_matcher is not None:
            track = model.get_value(iter, 0)
            return self._filter_matcher.match(trax.SearchResultTrack(track))
        return True

    def on_header_button_press(self, widget, event):
        if event.triggers_context_menu():
            self.header_menu.popup(None, None, None, None, event.button, event.time)
            return True

    def on_columns_changed(self, widget):
        columns = [c.name for c in self.get_columns()[1:]]
        if columns != settings.get_option('gui/columns', []):
            settings.set_option('gui/columns', columns)

    def on_column_clicked(self, column):
        if self.model.data_loading:
            return
        order = None
        for col in self.get_columns()[1:]:
            if col.name == column.name:
                order = column.get_sort_order()
                if order == Gtk.SortType.ASCENDING:
                    order = Gtk.SortType.DESCENDING
                else:
                    order = Gtk.SortType.ASCENDING
                col.set_sort_indicator(True)
                col.set_sort_order(order)

                self._sort_columns.insert(0, column.name)
            else:
                col.set_sort_indicator(False)
                col.set_sort_order(Gtk.SortType.DESCENDING)
        reverse = order == Gtk.SortType.DESCENDING

        # Uniquify the list of sort columns
        def unique_ordered(seq):
            seen = set()
            return [x for x in seq if x not in seen and not seen.add(x)]

        self._sort_columns = unique_ordered(self._sort_columns)

        # If you don't unselect before sorting, a large number of selected will
        # kill performance
        self.get_selection().unselect_all()
        with self.handler_block(self._cursor_changed):
            self.playlist.sort(self._sort_columns, reverse=reverse)

    def on_option_set(self, typ, obj, data):
        if data == "gui/columns" or data == 'gui/playlist_font':
            self._refresh_columns()

    def on_playback_start(self, type, player, track):
        if (
            player.queue.current_playlist == self.playlist
            and player.current == self.playlist.current
            and settings.get_option('gui/ensure_visible', True)
        ):
            self.scroll_to_current()

    def scroll_to_current(self):
        position = self.playlist.current_position
        if position >= 0:
            model = self.get_model()
            # If it's a filter, then the position isn't actually the path
            if hasattr(model, 'convert_child_path_to_path'):
                path = model.convert_child_path_to_path(Gtk.TreePath((position,)))
            if path:
                self.scroll_to_cell(path)
                self.set_cursor(path)

    def on_cursor_changed(self, widget):
        context = common.LazyDict(self)
        context['selection-empty'] = (
            lambda name, parent: parent.get_selection_count() == 0
        )
        context['selected-items'] = lambda name, parent: parent.get_selected_items()
        context['selected-tracks'] = lambda name, parent: parent.get_selected_tracks()
        context['selection-count'] = lambda name, parent: parent.get_selection_count()
        event.log_event('playlist_cursor_changed', self, context)

    def on_row_activated(self, *args):
        try:
            position, track = self.get_selected_items()[0]
        except IndexError:
            return

        # Call with restart_if_playing flag set to True, so that
        # currently-playing track will be restarted
        self._play_track_at(position, track, True, True)

    def on_row_inserted(self, model, path, iter):
        """
        When something is inserted into the playlist, focus on it. If
        there are multiple things inserted, focus only on the first.
        """
        if not self._insert_focusing:
            self._insert_focusing = True
            # HACK: GI: We get a segfault if we don't do this, because the
            # GtkTreePath gets deleted before the idle function is run.
            path = path.copy()

            def _set_cursor():
                self.set_cursor(path)
                self._insert_focusing = False

            GLib.idle_add(_set_cursor)

    def do_button_press_event(self, e):
        """
        Adds some custom selection work to
        1) unselect all rows if clicking an empty area,
        2) updating the selection upon right click and
        3) popping up the context menu upon right click

        Also sets the internal state for button pressed

        Taken from the following sources:

        * thunar_details_view_button_press_event() of thunar-details-view.c
        * MultiDragTreeView.__button_press/__button.release of quodlibet/qltk/views.py
        """

        # need this to workaround bug in GTK+ on OSX when dragging/dropping
        # -> https://bugzilla.gnome.org/show_bug.cgi?id=722815
        if self._hack_is_osx:
            self._hack_osx_control_mask = (
                True if e.state & Gdk.ModifierType.CONTROL_MASK else False
            )

        selection = self.get_selection()
        pathtuple = self.get_path_at_pos(int(e.x), int(e.y))
        # We only need the tree path if present
        if pathtuple:
            path = pathtuple[0]
            col = pathtuple[1]
        else:
            path = None

        # We unselect all selected items if the user clicks on an empty
        # area of the treeview and no modifier key is active
        if not e.state & Gtk.accelerator_get_default_mod_mask() and not path:
            selection.unselect_all()

        if path and e.type == Gdk.EventType.BUTTON_PRESS:
            # Prevent unselection of all except the clicked item on left
            # clicks, required to preserve the selection for DnD
            if (
                e.button == Gdk.BUTTON_PRIMARY
                and not e.state & Gtk.accelerator_get_default_mod_mask()
                and selection.path_is_selected(path)
            ):

                if selection.count_selected_rows() > 1:
                    selection.set_select_function(lambda *args: False, None)
                    self.pending_event = (path, col)
                elif hasattr(col, 'could_edit') and col.could_edit(self, path, e):
                    # TODO: should cache this?
                    tm = self.get_settings().props.gtk_double_click_time
                    if self.pending_edit_id:
                        GLib.source_remove(self.pending_edit_id)
                    self.pending_edit_data = (path, col)
                    self.pending_edit_ok = False
                    self.pending_edit_id = GLib.timeout_add(
                        tm, self._editing_double_click_ok
                    )

            if e.triggers_context_menu():
                # Select the path on which the user clicked if not selected yet
                if not selection.path_is_selected(path):
                    # We don't unselect all other items if Control is active
                    if not e.state & Gdk.ModifierType.CONTROL_MASK:
                        selection.unselect_all()

                    selection.select_path(path)

                self.menu.popup(None, None, None, None, e.button, e.time)

                return True

        elif e.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            self._cancel_editing()

        return Gtk.TreeView.do_button_press_event(self, e)

    def do_button_release_event(self, e):
        """
        Unsets the internal state for button press
        """
        self._hack_osx_control_mask = False

        # Restore regular selection behavior in any case
        self.get_selection().set_select_function(lambda *args: True, None)

        if self.pending_event:
            path, col = self.pending_event
            # perform the normal selection that would have happened
            self.set_cursor(path, col, 0)
            self.pending_event = None

        self._maybe_start_editing()

        return Gtk.TreeView.do_button_release_event(self, e)

    def _cancel_editing(self):
        self.pending_edit_ok = False
        self.pending_edit_data = None
        if self.pending_edit_id:
            GLib.source_remove(self.pending_edit_id)
            self.pending_edit_id = None

    def _editing_double_click_ok(self):
        self.pending_edit_id = None
        self._maybe_start_editing()
        return False

    def _maybe_start_editing(self):
        # this has to be called twice for an edit to start
        # -> either by the double click timeout, or button release
        if self.pending_edit_ok:
            path, col = self.pending_edit_data
            col.start_editing(self, path)
            self.pending_edit_ok = False
            self.pending_edit_data = None
        elif self.pending_edit_data:
            self.pending_edit_ok = True

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Menu:
            self.menu.popup(None, None, None, None, 0, event.time)
            return True

        elif event.keyval == Gdk.KEY_Delete:
            indexes = [x[0] for x in self.get_selected_paths()]
            with guiutil.without_model(self):
                if indexes and indexes == list(
                    range(indexes[0], indexes[0] + len(indexes))
                ):
                    del self.playlist[indexes[0] : indexes[0] + len(indexes)]
                else:
                    for i in indexes[::-1]:
                        del self.playlist[i]

        # TODO: localization?
        # -> Also, would be good to expose these shortcuts somehow to the user...
        #    it seems that Gtk.BindingSet is the way to do it, but there isn't a
        #    mechanism to enumerate it in python
        elif event.keyval == Gdk.KEY_q:
            if self.playlist is not self.player.queue:
                self.player.queue.extend(self.get_selected_tracks())

        elif event.keyval == Gdk.KEY_Up and event.state & Gdk.ModifierType.MOD1_MASK:
            indexes = [x[0] for x in self.get_selected_paths()]
            if len(indexes) == 1 and indexes[0] != 0:
                idx = indexes[0]
                track = self.playlist.pop(idx)
                self.playlist[idx - 1 : idx - 1] = [track]

        elif event.keyval == Gdk.KEY_Down and event.state & Gdk.ModifierType.MOD1_MASK:
            indexes = [x[0] for x in self.get_selected_paths()]
            if len(indexes) == 1 and indexes[0] != len(self.playlist) - 1:
                idx = indexes[0]
                track = self.playlist.pop(idx)
                self.playlist[idx + 1 : idx + 1] = [track]

        elif event.keyval == Gdk.KEY_F2:
            path, column = self.get_cursor()
            if path and isinstance(column, playlist_columns.EditableColumn):
                column.start_editing(self, path)

        # Prevent space-key from triggering 'row-activated' signal,
        # which restarts the currently-playing track. Instead, we call
        # _play_track_at() here with restart_if_playing flag set to
        # False, so that pause will be always toggled instead.
        elif event.keyval == Gdk.KEY_space:
            try:
                position, track = self.get_selected_items()[0]
            except IndexError:
                return True  # Prevent 'row-activated'

            self._play_track_at(position, track, True, False)

            return True  # Prevent 'row-activated'

        # Columns with editable rows will take row-activated and start editing
        # but we want to start playback, so simulate it instead
        elif event.keyval == Gdk.KEY_Return:
            self.on_row_activated()
            return True  # Prevent 'row-activated'

    def on_header_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Menu:
            # Open context menu for selecting visible columns
            m = menu.ProviderMenu('playlist-columns-menu', self)
            m.popup(None, None, None, None, 0, event.time)
            return True

    ### DND handlers ###
    # Source
    def on_drag_begin(self, widget, context):
        """
        Activates the dragging state
        """
        # TODO: set drag icon
        self.dragging = True
        self.pending_event = None
        self._cancel_editing()
        self.get_selection().set_select_function(lambda *args: True, None)

    def on_drag_data_get(self, widget, context, selection, info, etime):
        """
        Stores indices and URIs of the selected items in the drag selection
        """
        target_atom = selection.get_target()
        target = target_atom.name()
        if target == "exaile-index-list":
            positions = self.get_selected_paths()
            if positions:
                s = ",".join(str(i[0]) for i in positions)
                selection.set(target_atom, 8, s.encode('utf-8'))
        elif target == "text/uri-list":
            tracks = self.get_selected_tracks()
            uris = trax.util.get_uris_from_tracks(tracks)
            selection.set_uris(uris)

    def on_drag_data_delete(self, widget, context):
        """
        Stops the default handler from running, all
        processing occurs in the drag-data-received handler
        """
        self.stop_emission_by_name('drag-data-delete')

    def on_drag_end(self, widget, context):
        """
        Deactivates the dragging state
        """
        self.dragging = False

    # Dest
    def on_drag_drop(self, widget, context, x, y, etime):
        """
        Always allows processing of drop operations
        """
        return True

    def on_drag_data_received(self, widget, context, x, y, selection, info, etime):
        """
        Builds a list of tracks either from internal indices or
        external URIs and inserts or appends them to the playlist
        """
        # Stop default handler from running
        self.stop_emission_by_name('drag-data-received')

        # Makes `self.on_row_inserted` to ignore inserted rows
        # see https://github.com/exaile/exaile/issues/487
        self._insert_focusing = True

        drop_info = self.get_dest_row_at_pos(x, y)

        if drop_info:
            path, position = drop_info
            model = self.get_model()
            if isinstance(model, Gtk.TreeModelFilter):
                path = model.convert_path_to_child_path(path)

            insert_position = path[0]
            if position in (
                Gtk.TreeViewDropPosition.AFTER,
                Gtk.TreeViewDropPosition.INTO_OR_AFTER,
            ):
                insert_position += 1
        else:
            insert_position = -1

        # hack: see https://github.com/exaile/exaile/issues/479
        if self._hack_is_osx:
            source_widget = Gtk.drag_get_source_widget(context)
            if not (source_widget is None or source_widget is self) and hasattr(
                source_widget, 'get_selected_tracks'
            ):
                try:
                    tracks = source_widget.get_selected_tracks()
                    if insert_position >= 0:
                        self.playlist[insert_position:insert_position] = tracks
                    else:
                        self.playlist.extend(tracks)
                        insert_position = len(self.playlist) - len(tracks)
                except Exception:
                    pass  # Any exception on hack is ignored
                else:
                    # Select inserted items
                    if tracks:
                        self.selection.unselect_all()
                        self.selection.select_range(
                            self.model.get_path(
                                self.model.iter_nth_child(None, insert_position)
                            ),
                            self.model.get_path(
                                self.model.iter_nth_child(
                                    None, insert_position + len(tracks) - 1
                                )
                            ),
                        )

                    # Restore state to `self.on_row_inserted` do not ignore inserted rows
                    # see https://github.com/exaile/exaile/issues/487
                    self._insert_focusing = False
                    return

        tracks = []
        playlist = []
        positions = []
        pos = 0
        source_playlist_view = None

        target = selection.get_target().name()
        if target == "exaile-index-list":
            selection_data = selection.get_data().decode('utf-8')
            if selection_data == '':  # Ignore drops from empty areas
                # Restore state to `self.on_row_inserted` do not ignore inserted rows
                # see https://github.com/exaile/exaile/issues/487
                self._insert_focusing = False
                return
            positions = [int(pos) for pos in selection_data.split(",")]
            tracks = common.MetadataList()
            source_playlist_view = Gtk.drag_get_source_widget(context)
            playlist = self.playlist

            # Get the playlist of the
            if source_playlist_view is not self:
                playlist = source_playlist_view.playlist

            current_position_index = -1
            for i, pos in enumerate(positions):
                if pos == playlist.current_position:
                    current_position_index = i

                tracks.append(playlist[pos])

            # Insert at specific position if possible
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks

                if source_playlist_view is self:
                    # Update position for tracks after the insert position
                    for i, position in enumerate(positions[:]):
                        if position >= insert_position:
                            position += len(tracks)
                            positions[i] = position

                # Update playlist current position
                if current_position_index >= 0:
                    self.playlist.current_position = (
                        insert_position + current_position_index
                    )
                    self.model.update_row_params(self.playlist.current_position)
            else:
                # Otherwise just append the tracks
                self.playlist.extend(tracks)
                insert_position = len(self.playlist) - len(tracks)
        elif target == "text/uri-list":
            uris = selection.get_uris()
            tracks = []
            for uri in uris:
                if is_valid_playlist(uri):
                    tracks.extend(import_playlist(uri))
                else:
                    tracks.extend(trax.get_tracks_from_uri(uri))
            sort_by, reverse = self.get_sort_by()
            tracks = trax.sort_tracks(
                sort_by, tracks, reverse=reverse, artist_compilations=True
            )
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks
            else:
                self.playlist.extend(tracks)
                insert_position = len(self.playlist) - len(tracks)

        # Remove tracks from the source playlist if moved
        if context.get_selected_action() == Gdk.DragAction.MOVE:
            for i in positions[::-1]:
                del playlist[i]

        delete = context.get_selected_action() == Gdk.DragAction.MOVE
        context.finish(True, delete, etime)

        scroll_when_appending_tracks = settings.get_option(
            'gui/scroll_when_appending_tracks', False
        )

        if scroll_when_appending_tracks and tracks:
            self.scroll_to_cell(self.playlist.index(tracks[-1]))
        elif 0 < len(tracks) <= 500:
            # Keep insert position and length of selection for restoring after updating the playlist view
            if (
                0 < pos < insert_position
                and source_playlist_view is self
                and context.get_selected_action() == Gdk.DragAction.MOVE
            ):
                insert_position -= len(tracks)
            self._insert_row = insert_position
            self._insert_count = len(tracks)

        # Restore state to `self.on_row_inserted` do not ignore inserted rows
        # see https://github.com/exaile/exaile/issues/487
        self._insert_focusing = False

    def on_drag_motion(self, widget, context, x, y, etime):
        """
        Makes sure tracks can only be inserted before or after tracks
        and sets the drop action to move or copy depending on target
        and user interaction (e.g. Ctrl key)
        """
        drop_info = self.get_dest_row_at_pos(x, y)

        if not drop_info:
            return False

        path, position = drop_info

        if position == Gtk.TreeViewDropPosition.INTO_OR_BEFORE:
            position = Gtk.TreeViewDropPosition.BEFORE
        elif position == Gtk.TreeViewDropPosition.INTO_OR_AFTER:
            position = Gtk.TreeViewDropPosition.AFTER

        self.set_drag_dest_row(path, position)

        action = Gdk.DragAction.MOVE
        _, _, _, modifier = self.get_window().get_pointer()
        target = self.drag_dest_find_target(context, None).name()

        if (
            target == 'text/uri-list'
            or (self._hack_is_osx and self._hack_osx_control_mask)
            or (not self._hack_is_osx and modifier & Gdk.ModifierType.CONTROL_MASK)
        ):
            action = Gdk.DragAction.COPY

        if self.dragdrop_copyonly and Gtk.drag_get_source_widget(context) != self:
            action = Gdk.DragAction.COPY

        Gdk.drag_status(context, action, etime)

        return True

    def on_size_allocate(self, plView, selection):
        if self._insert_row > -1:
            # correction of selected rows
            self.select_rows(
                self._insert_row, self._insert_row + self._insert_count - 1
            )
            self._insert_row = -1
            self._insert_count = 0

    def show_properties_dialog(self):
        from xlgui import properties

        items = self.get_selected_items()

        # If only one track is selected, we expand `tracks` to include all
        # tracks in the playlist... except for really large playlists, this
        # essentially hangs. Instead, only show all tracks *if* the playlist
        # size is less than 100.
        #
        # A better option would be to lazy load the files, but I'm too lazy
        # to implement that now.. :)

        if len(items) == 1 and len(self.playlist) < 100:
            tracks = self.playlist[:]
            current_position = items[0][0]
        else:
            tracks = [i[1] for i in items]
            current_position = 0

        properties.TrackPropertiesDialog(self.get_toplevel(), tracks, current_position)

    def on_provider_removed(self, provider):
        """
        Called when a column provider is removed
        """
        columns = settings.get_option('gui/columns')

        if provider.name in columns:
            columns.remove(provider.name)
            settings.set_option('gui/columns', columns)

    def select_rows(self, start, stop):
        self.selection.unselect_all()
        if self.model.iter_nth_child(None, start) == None:
            return
        if self.model.iter_nth_child(None, stop) == None:
            return
        self.selection.select_range(
            self.model.get_path(self.model.iter_nth_child(None, start)),
            self.model.get_path(self.model.iter_nth_child(None, stop)),
        )


class PlaylistModel(Gtk.ListStore):
    """
    This ListStore contains all the information needed to render a playlist
    via a PlaylistView. There are five columns:

    * xl.trax.Track
    * dictionary (tag cache)
    * Gdk.Pixbuf (indicates whether track is playing or not)
    * boolean (indicates whether row is sensitive)
    * Pango.Weight (indicates if row is the playing track or not)

    The cache keys correspond to the tags rendered by each column. When a
    track changes, the row's corresponding cache is cleared and the row
    change event is fired.

    The cache keys are populated by the playlist columns. This arrangement
    ensures that we don't have to recreate the playlist model each time the
    columns are changed.
    """

    __gsignals__ = {
        # Called with true indicates starting operation, False ends op
        'data-loading': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_BOOLEAN,))
    }

    COL_TRACK = 0
    COL_CACHE = 1
    COL_PIXBUF = 2
    COL_SENSITIVE = 3
    COL_WEIGHT = 4

    PARAM_COLS = (COL_PIXBUF, COL_SENSITIVE, COL_WEIGHT)

    def __init__(self, playlist, column_names, player, parent):
        # columns: Track, Pixbuf, dict (cache)
        Gtk.ListStore.__init__(
            self, object, object, GdkPixbuf.Pixbuf, bool, Pango.Weight
        )
        self.playlist = playlist
        self.player = player

        self._set_columns(column_names)

        self.data_loading = False
        self.data_load_queue = []

        self._redraw_timer = None
        self._redraw_queue = []

        event.add_ui_callback(
            self.on_tracks_added, "playlist_tracks_added", playlist, destroy_with=parent
        )
        event.add_ui_callback(
            self.on_tracks_removed,
            "playlist_tracks_removed",
            playlist,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_current_position_changed,
            "playlist_current_position_changed",
            playlist,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_spat_position_changed,
            "playlist_spat_position_changed",
            playlist,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_track_start",
            self.player,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_track_end",
            self.player,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_player_pause",
            self.player,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_playback_state_change,
            "playback_player_resume",
            self.player,
            destroy_with=parent,
        )
        event.add_ui_callback(
            self.on_track_tags_changed, "track_tags_changed", destroy_with=parent
        )

        event.add_ui_callback(self.on_option_set, "gui_option_set", destroy_with=parent)

        self._setup_icons()
        self.on_tracks_added(
            None, self.playlist, list(enumerate(self.playlist))
        )  # populate the list

    def _set_columns(self, column_names):
        self.column_names = set(column_names)

    def _setup_icons(self):
        self.play_pixbuf = icons.ExtendedPixbuf(
            icons.MANAGER.pixbuf_from_icon_name('media-playback-start')
        )
        self.pause_pixbuf = icons.ExtendedPixbuf(
            icons.MANAGER.pixbuf_from_icon_name('media-playback-pause')
        )
        self.stop_pixbuf = icons.ExtendedPixbuf(
            icons.MANAGER.pixbuf_from_icon_name('media-playback-stop')
        )
        stop_overlay_pixbuf = self.stop_pixbuf.scale_simple(
            dest_width=self.stop_pixbuf.pixbuf.get_width() // 2,
            dest_height=self.stop_pixbuf.pixbuf.get_height() // 2,
            interp_type=GdkPixbuf.InterpType.BILINEAR,
        )
        stop_overlay_pixbuf = stop_overlay_pixbuf.move(
            offset_x=stop_overlay_pixbuf.pixbuf.get_width(),
            offset_y=stop_overlay_pixbuf.pixbuf.get_height(),
            resize=True,
        )
        self.play_stop_pixbuf = self.play_pixbuf & stop_overlay_pixbuf
        self.pause_stop_pixbuf = self.pause_pixbuf & stop_overlay_pixbuf
        self.clear_pixbuf = self.play_pixbuf.copy()
        self.clear_pixbuf.pixbuf.fill(0x00000000)

        font = settings.get_option('gui/playlist_font', None)
        if font is not None:
            # get default font
            default = float(Gtk.Widget.get_default_style().font_desc.get_size())
            new_font = Pango.FontDescription(font).get_size()

            # scale pixbuf accordingly
            t = GdkPixbuf.InterpType.BILINEAR
            s = max(int(self.play_pixbuf.get_width() * (new_font / default)), 1)

            self.play_pixbuf = self.play_pixbuf.scale_simple(s, s, t)
            self.pause_pixbuf = self.pause_pixbuf.scale_simple(s, s, t)
            self.stop_pixbuf = self.stop_pixbuf.scale_simple(s, s, t)
            self.play_stop_pixbuf = self.play_stop_pixbuf.scale_simple(s, s, t)
            self.pause_stop_pixbuf = self.pause_stop_pixbuf.scale_simple(s, s, t)
            self.clear_pixbuf = self.clear_pixbuf.scale_simple(s, s, t)

    def _refresh_icons(self):
        self._setup_icons()
        itr = self.get_iter_first()
        position = 0
        while itr:
            self.set(itr, self.PARAM_COLS, self._compute_row_params(position))
            itr = self.iter_next(itr)
            position += 1

    def on_option_set(self, typ, obj, data):
        if data == "gui/playlist_font":
            self._refresh_icons()

    def _compute_row_params(self, rowidx):
        """
        :returns: pixbuf, sensitive, weight
        """

        pixbuf = self.clear_pixbuf.pixbuf
        weight = Pango.Weight.NORMAL
        sensitive = True

        playlist = self.playlist

        spatpos = playlist.spat_position
        spat = spatpos == rowidx

        if spat:
            pixbuf = self.stop_pixbuf.pixbuf

        if playlist is self.player.queue.current_playlist:

            if (
                playlist.current_position == rowidx
                and playlist[rowidx] == self.player.current
            ):

                # this row is the current track, set a special icon
                state = self.player.get_state()

                weight = Pango.Weight.HEAVY

                if state == 'playing':
                    if spat:
                        pixbuf = self.play_stop_pixbuf.pixbuf
                    else:
                        pixbuf = self.play_pixbuf.pixbuf
                elif state == 'paused':
                    if spat:
                        pixbuf = self.pause_stop_pixbuf.pixbuf
                    else:
                        pixbuf = self.pause_pixbuf.pixbuf

            if spatpos == -1 or spatpos > rowidx:
                sensitive = True
            else:
                sensitive = False

        return pixbuf, sensitive, weight

    def update_row_params(self, position):
        itr = self.iter_nth_child(None, position)
        if itr is not None:
            self.set(itr, self.PARAM_COLS, self._compute_row_params(position))

    ### Event callbacks to keep the model in sync with the playlist ###

    def on_tracks_added(self, event_type, playlist, tracks):
        self._load_data(tracks)

    def on_tracks_removed(self, event_type, playlist, tracks):
        for position, track in reversed(tracks):
            self.remove(self.iter_nth_child(None, position))

    def on_current_position_changed(self, event_type, playlist, positions):
        for position in positions:
            if position < 0:
                continue
            self.update_row_params(position)

    def on_spat_position_changed(self, event_type, playlist, positions):
        pos = min(positions)

        if pos < 0:
            pos = 0
            itr = self.get_iter_first()
        else:
            itr = self.iter_nth_child(None, pos)

        while itr:
            self.set(itr, self.PARAM_COLS, self._compute_row_params(pos))
            itr = self.iter_next(itr)
            pos += 1

    def on_playback_state_change(self, event_type, player_obj, track):
        position = self.playlist.current_position
        if position < 0 or position >= len(self):
            return
        self.update_row_params(position)

    def on_track_tags_changed(self, type, track, tags):
        if (
            not track
            or not settings.get_option('gui/sync_on_tag_change', True)
            or not (tags & self.column_names)
        ):
            return

        if self._redraw_timer:
            GLib.source_remove(self._redraw_timer)
        self._redraw_queue.append(track)
        self._redraw_timer = GLib.timeout_add(100, self._on_track_tags_changed)

    def _on_track_tags_changed(self):
        self._redraw_timer = None
        redraw_queue = set(self._redraw_queue)
        self._redraw_queue = []

        COL_TRACK = self.COL_TRACK
        COL_CACHE = self.COL_CACHE

        for row in self:
            if row[COL_TRACK] in redraw_queue:
                row[COL_CACHE].clear()
                self.row_changed(row.path, row.iter)

    #
    # Loading data into the playlist:
    #
    # - Profiler reveals that most of the playlist loading time is spent in two
    #   places
    #   - Formatting values
    #   - Converting them to GValue objects for insert into the treeview
    #
    # Now, the program is annoyingly blocked when this happens, so we need to
    # process new tracks on a different thread, and show some kind of loading
    # indicator instead. That's what these four functions help us do.
    #

    def _load_data(self, tracks):

        # Don't allow race condition between adds.. there's probably a race
        # condition for removal
        if self.data_loading:
            self.data_load_queue.extend(tracks)
            return

        self.data_loading = True
        self.emit('data-loading', True)

        if len(tracks) > 500:
            self._load_data_thread(tracks)
        else:
            render_data = self._load_data_fn(tracks)
            self._load_data_done(render_data)

    @common.threaded
    def _load_data_thread(self, tracks):
        render_data = self._load_data_fn(tracks)
        GLib.idle_add(self._load_data_done, render_data)

    def _load_data_fn(self, tracks):
        indices = (0, 1, 2, 3, 4)
        return [
            (position, indices, (track, {}) + self._compute_row_params(position))
            for position, track in tracks
        ]

    def _load_data_done(self, render_data):
        for args in render_data:
            self.insert_with_valuesv(*args)

        self.data_loading = False
        self.emit('data-loading', False)

        if self.data_load_queue:
            tracks = self.data_load_queue
            self.data_load_queue = []

            self._load_data(tracks)
