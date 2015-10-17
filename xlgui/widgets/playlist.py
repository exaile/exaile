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

from itertools import izip
import logging
import sys

from xl.nls import gettext as _
from xl.playlist import (
    Playlist,    
    is_valid_playlist,
    import_playlist,
)
from xl import (
    common,
    event,
    main,
    player,
    providers,
    settings,
    trax,
    xdg
)

from xlgui.widgets.common import AutoScrollTreeView
from xlgui.widgets.notebook import NotebookPage
from xlgui.widgets import (
    dialogs,
    menu,
    menuitems,
    playlist_columns
)
from xlgui import (
    guiutil,
    icons
)

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
        image = Gtk.Image.new_from_icon_name('media-playlist-'+self.modetype,
                size=Gtk.IconSize.MENU)
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
        item = Gtk.ImageMenuItem.new_with_mnemonic(_('Remove _Current Track From Playlist'))
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
        context['playlist'].randomize(positions)

# do this in a function to avoid polluting the global namespace
def __create_playlist_tab_context_menu():
    smi = menu.simple_menu_item
    sep = menu.simple_separator
    items = []
    items.append(smi('new-tab', [], _("_New Playlist"), 'tab-new',
        lambda w, n, o, c: o.tab.notebook.create_new_playlist()))
    items.append(sep('new-tab-sep', ['new-tab']))
    
    # TODO: These two probably shouldn't reach back to main.. 
    def _save_playlist_cb(widget, name, page, context):
        main.exaile().playlists.save_playlist(page.playlist, overwrite=True)
        
    def _saveas_playlist_cb(widget, name, page, context):
        exaile = main.exaile()
        playlists = exaile.playlists
        name = dialogs.ask_for_playlist_name(
            exaile.gui.main.window, playlists, page.playlist.name)
        if name is not None:
            page.set_page_name(name)
            playlists.save_playlist(page.playlist)
    
    items.append(smi('save', ['new-tab-sep'], _("_Save"), 'document-save',
        _save_playlist_cb,
        condition_fn=lambda n, p, c: main.exaile().playlists.has_playlist_name(p.playlist.name)))
    items.append(smi('saveas', ['save'], _("Save _As"), 'document-save-as',
        _saveas_playlist_cb))
    items.append(smi('rename', ['saveas'], _("_Rename"), None,
        lambda w, n, o, c: o.tab.start_rename()))
    items.append(smi('clear', ['rename'], _("_Clear"), 'edit-clear-all',
        lambda w, n, o, c: o.playlist.clear()))
    items.append(sep('tab-close-sep', ['clear']))
    
    def _get_pl_func(o, c):
        return o.playlist
    
    items.append(menuitems.ExportPlaylistMenuItem('export', ['tab-close-sep'], _get_pl_func))
    items.append(menuitems.ExportPlaylistFilesMenuItem('export-files', ['export'], _get_pl_func))
    items.append(sep('tab-export-sep', ['export']))
    items.append(smi('tab-close', ['tab-export-sep'], _("Close _Tab"), 'window-close',
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
        context['playlist'] = lambda name, parent: parent.playlist
        context['selection-empty'] = lambda name, parent: parent.get_selection_count() == 0
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
                icon_name = 'media-playback-play'

        menuitem = Gtk.ImageMenuItem.new_with_mnemonic(display_name)
        menuitem.set_image(Gtk.Image.new_from_icon_name(icon_name,
            Gtk.IconSize.MENU))
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
    items.append(smi('remove', [items[-1].name], _("_Remove from Playlist"),
        'list-remove', remove_tracks_cb))

    items.append(RandomizeMenuItem([items[-1].name]))

    def playlist_menu_condition(name, parent, context):
        """
            Returns True if the containing notebook's tab bar is hidden
        """
        scrolledwindow = parent.get_parent()
        page = scrolledwindow.get_parent()
        return not page.tab.notebook.get_show_tabs()

    items.append(smi('playlist-menu', [items[-1].name], _('Playlist'),
        submenu=menu.ProviderMenu('playlist-tab-context-menu', None),
        condition_fn=playlist_menu_condition))

    items.append(sep('sep2', [items[-1].name]))

    items.append(smi('properties', [items[-1].name], _("_Track Properties"),
        'document-properties', lambda w, n, o, c: o.show_properties_dialog()))

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
        
        self.loading = None
        self.loading_timer = None

        uifile = xdg.get_data_path("ui", "playlist.ui")
        self.builder = Gtk.Builder()
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
        self.view.connect('button-press-event', self.on_view_button_press_event)
        self.view.model.connect('row-changed', self.on_row_changed)
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

    def on_shuffle_button_press_event(self, widget, event):
        self.__show_toggle_menu(Playlist.shuffle_modes,
                Playlist.shuffle_mode_names, self.on_shuffle_mode_set,
                'shuffle_mode', widget, event)
                
    def on_shuffle_button_popup_menu(self, widget):
        self.__show_toggle_menu(Playlist.shuffle_modes,
                Playlist.shuffle_mode_names, self.on_shuffle_mode_set,
                'shuffle_mode', widget, None)
        return True

    def on_repeat_button_press_event(self, widget, event):
        self.__show_toggle_menu(Playlist.repeat_modes,
                Playlist.repeat_mode_names, self.on_repeat_mode_set,
                'repeat_mode', widget, event)
                
    def on_repeat_button_popup_menu(self, widget):
        self.__show_toggle_menu(Playlist.repeat_modes,
                Playlist.repeat_mode_names, self.on_repeat_mode_set,
                'repeat_mode', widget, None)
        return True

    def on_dynamic_button_toggled(self, widget):
        if widget.get_active():
            self.playlist.dynamic_mode = self.playlist.dynamic_modes[1]
        else:
            self.playlist.dynamic_mode = self.playlist.dynamic_modes[0]

    def on_search_entry_activate(self, entry):
        filter_string = entry.get_text()
        if filter_string == "":
            self.view.filter_tracks(None)
        else:
            self.view.filter_tracks(filter_string)


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
        menu.show_all()
        if event is not None:
            menu.popup(None, None, guiutil.position_menu, (self.get_window(), widget), 
                        event.button, event.time)
        else:
            menu.popup(None, None, guiutil.position_menu, (self.get_window(), widget),
                        0, 0)
        menu.reposition()

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
        GLib.idle_add(button.set_active, mode != 'disabled')

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

        GLib.idle_add(self.dynamic_button.set_sensitive, sensitive)
        GLib.idle_add(self.dynamic_button.set_tooltip_text, tooltip_text)

    def on_option_set(self, evtype, settings, option):
        """
            Handles option changes
        """
        if option == 'gui/playlist_utilities_bar_visible':
            visible = settings.get_option(option, True)
            GLib.idle_add(self.playlist_utilities_bar.set_visible, visible)
            GLib.idle_add(self.playlist_utilities_bar.set_sensitive, visible)
            GLib.idle_add(self.playlist_utilities_bar.set_no_show_all, not visible)

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
            
    def on_data_loading(self, model, loading):
        '''Called when tracks are being loaded into the model'''
        if loading:
            if self.loading is None and self.loading_timer is None:
                self.loading_timer = GLib.timeout_add(500, self.on_data_loading_timer)
        else:
            if self.loading_timer is not None:
                GLib.source_remove(self.loading_timer)
                self.loading_timer = None
            
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
        selection = view.get_selection()
        path = view.get_path_at_pos(int(e.x), int(e.y))
        # We only need the tree path if present
        path = path[0] if path else None

        if not path and e.type == Gdk.EventType.BUTTON_PRESS and e.button == 3:
            self.tab_menu.popup(None, None, None, None, e.button, e.time)

class PlaylistView(AutoScrollTreeView, providers.ProviderHandler):
    __gsignals__ = {}

    def __init__(self, playlist, player):
        AutoScrollTreeView.__init__(self)
        providers.ProviderHandler.__init__(self, 'playlist-columns')

        self.playlist = playlist
        self.player = player
        self.menu = PlaylistContextMenu(self)
        self.tabmenu = menu.ProviderMenu('playlist-tab-context-menu', self)
        self.dragging = False
        self.pending_event = None
        self.button_pressed = False # used by columns to determine whether
                                    # a notify::width event was initiated
                                    # by the user.
        self._insert_focusing = False
        
        self._hack_is_osx = sys.platform == 'darwin'
        self._hack_osx_control_mask = False

        # Set to true if you only want things to be copied here, not moved
        self.dragdrop_copyonly = False

        self.set_fixed_height_mode(True) # MASSIVE speedup - don't disable this!
        self.set_rules_hint(True)
        self.set_enable_search(True)
        self.selection = self.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        self._filter_matcher = None
        
        self._setup_columns()
        self.columns_changed_id = self.connect("columns-changed",
                self.on_columns_changed)

        self.targets = [Gtk.TargetEntry.new("exaile-index-list", Gtk.TargetFlags.SAME_APP, 0),
                Gtk.TargetEntry.new("text/uri-list", 0, 0)]
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, self.targets,
                Gdk.DragAction.COPY|Gdk.DragAction.MOVE)
        self.drag_dest_set(Gtk.DestDefaults.ALL, self.targets,
                Gdk.DragAction.COPY|Gdk.DragAction.DEFAULT|
                Gdk.DragAction.MOVE)

        event.add_callback(self.on_option_set, "gui_option_set")
        event.add_callback(self.on_playback_start, "playback_track_start", self.player)
        self.connect("cursor-changed", self.on_cursor_changed )
        self.connect("row-activated", self.on_row_activated)
        self.connect("key-press-event", self.on_key_press_event)

        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-drop", self.on_drag_drop)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.connect("drag-end", self.on_drag_end)
        self.connect("drag-motion", self.on_drag_motion)

    def filter_tracks(self, filter_string):
        '''
            Only show tracks that match the filter. If filter is None, then
            clear any existing filters.
            
            The filter will search any currently enabled columns AND the
            default columns. 
        '''
    
        if filter_string is None:
            self._filter_matcher = None
            self.modelfilter.refilter()
        else:
            # Merge default columns and currently enabled columns
            keyword_tags = set(playlist_columns.DEFAULT_COLUMNS + [c.name for c in self.get_columns()])
            self._filter_matcher = trax.TracksMatcher(filter_string,
                    case_sensitive=False,
                    keyword_tags=keyword_tags)
            logger.debug("Filtering playlist '%s' by '%s'." % (self.playlist.name, filter_string))
            self.modelfilter.refilter()
            logger.debug("Filtering playlist '%s' by '%s' completed." % (self.playlist.name, filter_string))
        
    def get_selection_count(self):
        '''
            Returns the number of items currently selected in the
            playlist. Prefer this to len(get_selected_tracks()) et al
            if you will discard the actual track list
        '''
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
                tracks = [(model.convert_path_to_child_path(path)[0], model.get_value(model.get_iter(path), 0)) for path in paths]
            else:
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
            reverse = sortcol.get_sort_order() == Gtk.SortType.DESCENDING
            sort_by = [sortcol.name] + list(common.BASE_SORT_TAGS)
        else:
            reverse = False
            sort_by = list(common.BASE_SORT_TAGS)
        return (sort_by, reverse)
        
    def play_track_at(self, position, track):
        '''
            When called, this will begin playback of a track at a given
            position in the internal playlist
        '''
        self._play_track_at(position, track)
        
    def _play_track_at(self, position, track, on_activated=False):
        '''Internal API'''       
        if not settings.get_option('playlist/enqueue_by_default', False) or \
                (self.playlist is self.player.queue and on_activated):
            if self.player.queue.is_play_enabled():        
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

        # FIXME: this is kinda ick because of supporting both models
        #self.model.columns = columns
        # TODO: What is the fixme talking about?
        self.model = PlaylistModel(self.playlist, columns, self.player)
        self.model.connect('row-inserted', self.on_row_inserted)
        self.set_model(self.model)
        self._setup_filter()

        font = settings.get_option('gui/playlist_font', None)
        if font is not None:
            font = Pango.FontDescription(font)
        
        for position, column in enumerate(columns):
            position += 2 # offset for pixbuf column
            playlist_column = providers.get_provider(
                'playlist-columns', column)(self, position, self.player, font)
            playlist_column.connect('clicked', self.on_column_clicked)
            self.append_column(playlist_column)
            header = playlist_column.get_widget()
            header.show()
            header.get_ancestor(Gtk.Button).connect('button-press-event',
                self.on_header_button_press)
                
            header.get_ancestor(Gtk.Button).connect('key-press-event',
                self.on_header_key_press_event)

    def _setup_filter(self):
        '''Call this anytime after you call set_model()'''
        self.modelfilter = self.get_model().filter_new()
        self.modelfilter.set_visible_func(self.modelfilter_visible_func)
        self.set_model(self.modelfilter)
        
        if self._filter_matcher is not None:
            self.modelfilter.refilter()
                
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
            m.popup(None, None, None, None, event.button, event.time)
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
                if order == Gtk.SortType.ASCENDING:
                    order = Gtk.SortType.DESCENDING
                else:
                    order = Gtk.SortType.ASCENDING
                col.set_sort_indicator(True)
                col.set_sort_order(order)
            else:
                col.set_sort_indicator(False)
                col.set_sort_order(Gtk.SortType.DESCENDING)
        reverse = order == Gtk.SortType.DESCENDING
        self.playlist.sort([column.name] + list(common.BASE_SORT_TAGS), reverse=reverse)

    def on_option_set(self, typ, obj, data):
        if data == "gui/columns" or data == 'gui/playlist_font':
            GLib.idle_add(self._refresh_columns, priority=GLib.PRIORITY_DEFAULT)

    def on_playback_start(self, type, player, track):
        if player.queue.current_playlist == self.playlist and \
                player.current == self.playlist.current and \
                settings.get_option('gui/ensure_visible', True):
            GLib.idle_add(self.scroll_to_current)

    def scroll_to_current(self):
        position = self.playlist.current_position
        if position >= 0:
            model = self.get_model()
            # If it's a filter, then the position isn't actually the path
            if hasattr(model, 'convert_child_path_to_path'):
                path = model.convert_child_path_to_path(Gtk.TreePath((position,)))
            self.scroll_to_cell(path)
            self.set_cursor(path)
        
    def on_cursor_changed(self, widget):
        context = common.LazyDict(self)
        context['selection-empty'] = lambda name, parent: parent.get_selection_count() == 0
        context['selected-items'] = lambda name, parent: parent.get_selected_items()
        context['selected-tracks'] = lambda name, parent: parent.get_selected_tracks()
        event.log_event( 'playlist_cursor_changed', self, context)
        

    def on_row_activated(self, *args):
        try:
            position, track = self.get_selected_items()[0]
        except IndexError:
            return

        self._play_track_at(position, track, True)
        
    def on_row_inserted(self, model, path, iter):
        '''
            When something is inserted into the playlist, focus on it. If 
            there are multiple things inserted, focus only on the first. 
        '''
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
        self.button_pressed = True
        self.grab_focus()
        
        # need this to workaround bug in GTK+ on OSX when dragging/dropping
        # -> https://bugzilla.gnome.org/show_bug.cgi?id=722815
        if self._hack_is_osx:
            self._hack_osx_control_mask = True if e.state & Gdk.ModifierType.CONTROL_MASK else False

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
            if e.button == 1 and not e.state & Gtk.accelerator_get_default_mod_mask() and \
               selection.path_is_selected(path):
                selection.set_select_function(lambda *args: False, None)
                self.pending_event = (path, col)

            # Open the context menu on right clicks
            if e.button == 3:
                # Select the path on which the user clicked if not selected yet
                if not selection.path_is_selected(path):
                    # We don't unselect all other items if Control is active
                    if not e.state & Gdk.ModifierType.CONTROL_MASK:
                        selection.unselect_all()

                    selection.select_path(path)

                self.menu.popup(None, None, None, None, e.button, e.time)

                return True

        return Gtk.TreeView.do_button_press_event(self, e)

    def do_button_release_event(self, e):
        """
            Unsets the internal state for button press
        """
        self.button_pressed = False
        self._hack_osx_control_mask = False
        
        # Restore regular selection behavior in any case
        self.get_selection().set_select_function(lambda *args: True, None)
        
        if self.pending_event:
            path, col = self.pending_event
            # perform the normal selection that would have happened
            self.set_cursor(path, col, 0)
            self.pending_event = None
        
        return Gtk.TreeView.do_button_release_event(self, e)

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Menu:
            self.menu.popup(None, None, None, None, 0, event.time)
            return True
            
        elif event.keyval == Gdk.KEY_Delete:
            indexes = [x[0] for x in self.get_selected_paths()]
            if indexes and indexes == range(indexes[0], indexes[0]+len(indexes)):
                del self.playlist[indexes[0]:indexes[0]+len(indexes)]
            else:
                for i in indexes[::-1]:
                    del self.playlist[i]
                    
    def on_header_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Menu:
            # Open context menu for selecting visible columns
            m = menu.ProviderMenu('playlist-columns-menu', self)
            m.popup(None, None, None, None, 0, event.time)
            return True

    ### DND handlers ###
    ## Source
    def on_drag_begin(self, widget, context):
        """
            Activates the dragging state
        """
        # TODO: set drag icon
        self.dragging = True
        self.pending_event = None

    def on_drag_data_get(self, widget, context, selection, info, etime):
        """
            Stores indices and URIs of the selected items in the drag selection
        """
        target = selection.get_target()
        if target == "exaile-index-list":
            positions = self.get_selected_paths()
            if positions:
                s = ",".join(str(i[0]) for i in positions)
                selection.set(target, 8, s)
        elif target == "text/uri-list":
            tracks = self.get_selected_tracks()
            uris = trax.util.get_uris_from_tracks(tracks)
            selection.set_uris(uris)

    def on_drag_data_delete(self, widget, context):
        """
            Stops the default handler from running, all
            processing occurs in the drag-data-received handler
        """
        self.stop_emission('drag-data-delete')

    def on_drag_end(self, widget, context):
        """
            Deactivates the dragging state
        """
        self.dragging = False

    ## Dest
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
        self.stop_emission('drag-data-received')

        drop_info = self.get_dest_row_at_pos(x, y)

        if drop_info:
            path, position = drop_info
            model = self.get_model()
            if isinstance(model, Gtk.TreeModelFilter):
                path = model.convert_path_to_child_path(path)
            
            insert_position = path[0]
            if position in (Gtk.TreeViewDropPosition.AFTER, Gtk.TreeViewDropPosition.INTO_OR_AFTER):
                insert_position += 1
        else:
            insert_position = -1

        tracks = []

        target = selection.get_target().name()
        if target == "exaile-index-list":
            positions = [int(x) for x in selection.data.split(",")]
            tracks = common.MetadataList()
            source_playlist_view = Gtk.drag_get_source_widget(context)
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
            if context.action == Gdk.DragAction.MOVE:
                for i in positions[::-1]:
                    del playlist[i]
        elif target == "text/uri-list":
            uris = selection.get_uris()
            tracks = []
            for uri in uris:
                if is_valid_playlist(uri):
                    tracks.extend(import_playlist(uri))
                else:
                    tracks.extend(trax.get_tracks_from_uri(uri))
            sort_by, reverse = self.get_sort_by()
            tracks = trax.sort_tracks(sort_by, tracks, reverse=reverse,
                artist_compilations=True)
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks
            else:
                self.playlist.extend(tracks)

        #delete = context.action == Gdk.DragAction.MOVE
        # TODO: Selected? Suggested?
        delete = context.get_selected_action() == Gdk.DragAction.MOVE
        context.finish(True, delete, etime)

        scroll_when_appending_tracks = settings.get_option(
            'gui/scroll_when_appending_tracks', False)

        if scroll_when_appending_tracks and tracks:
            self.scroll_to_cell(self.playlist.index(tracks[-1]))

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
        target = self.drag_dest_find_target(context, self.drag_dest_get_target_list()).name()

        if target == 'text/uri-list' or \
           (self._hack_is_osx and self._hack_osx_control_mask) or \
           (not self._hack_is_osx and modifier & Gdk.ModifierType.CONTROL_MASK):
            action = Gdk.DragAction.COPY
        
        if self.dragdrop_copyonly and Gtk.drag_get_source_widget(context) != self:
            action = Gdk.DragAction.COPY
        
        Gdk.drag_status(context, action, etime)

        return True

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
            with_extras = True
        else:
            tracks = [i[1] for i in items]
            current_position = 0
            with_extras = False
        
        properties.TrackPropertiesDialog(None, tracks,
                                         current_position, with_extras)

    def on_provider_removed(self, provider):
        """
            Called when a column provider is removed
        """
        columns = settings.get_option('gui/columns')

        if provider.name in columns:
            columns.remove(provider.name)
            settings.set_option('gui/columns', columns)

    def modelfilter_visible_func(self, model, iter, data):
        if self._filter_matcher is not None:
            track = model.get_value(iter, 0)
            return self._filter_matcher.match(trax.SearchResultTrack(track))
        return True

class PlaylistModel(Gtk.ListStore):

    __gsignals__ = {
        # Called with true indicates starting operation, False ends op
        'data-loading': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_BOOLEAN,)
        )
    }
    
    def __init__(self, playlist, columns, player):
        Gtk.ListStore.__init__(self, int) # real types are set later
        self.playlist = playlist
        self.columns = columns
        self.player = player
        
        self.data_loading = False
        self.data_load_queue = []

        self.coltypes = [object, GdkPixbuf.Pixbuf] + [providers.get_provider('playlist-columns', c).datatype for c in columns]
        self.set_column_types(self.coltypes)
        
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

        event.add_callback(self.on_option_set, "gui_option_set")
                
        self._setup_icons()
        self.on_tracks_added(None, self.playlist, list(enumerate(self.playlist))) # populate the list

    def _setup_icons(self):
        self.play_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(Gtk.STOCK_MEDIA_PLAY))
        self.pause_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(Gtk.STOCK_MEDIA_PAUSE))
        self.stop_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(Gtk.STOCK_STOP))
        stop_overlay_pixbuf = self.stop_pixbuf.scale_simple(
                dest_width=self.stop_pixbuf.pixbuf.get_width() / 2,
                dest_height=self.stop_pixbuf.pixbuf.get_height() / 2,
                interp_type=GdkPixbuf.InterpType.BILINEAR)
        stop_overlay_pixbuf = stop_overlay_pixbuf.move(
                offset_x=stop_overlay_pixbuf.pixbuf.get_width(),
                offset_y=stop_overlay_pixbuf.pixbuf.get_height(),
                resize=True)
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
            s = max(int(self.play_pixbuf.get_width() * (new_font/default)),1)
                
            self.play_pixbuf = self.play_pixbuf.scale_simple(s,s,t)
            self.pause_pixbuf = self.pause_pixbuf.scale_simple(s,s,t)
            self.stop_pixbuf = self.stop_pixbuf.scale_simple(s,s,t)
            self.play_stop_pixbuf = self.play_stop_pixbuf.scale_simple(s,s,t)
            self.pause_stop_pixbuf = self.pause_stop_pixbuf.scale_simple(s,s,t)
            self.clear_pixbuf = self.clear_pixbuf.scale_simple(s,s,t)
        
    def _refresh_icons(self):
        self._setup_icons()
        for i,row in enumerate(self):
            row[1] = self.icon_for_row(i).pixbuf
        
    def on_option_set(self, typ, obj, data):
        if data == "gui/playlist_font":
            GLib.idle_add(self._refresh_icons)

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
            self.set(iter, 1, self.icon_for_row(position).pixbuf)

    ### Event callbacks to keep the model in sync with the playlist ###

    def on_tracks_added(self, event_type, playlist, tracks):
        self._load_data(tracks)

    def on_tracks_removed(self, event_type, playlist, tracks):
        tracks.reverse()
        for position, track in tracks:
            self.remove(self.iter_nth_child(None, position))

    def on_current_position_changed(self, event_type, playlist, positions):
        for position in positions:
            if position < 0:
                continue
            GLib.idle_add(self.update_icon, position)

    def on_spat_position_changed(self, event_type, playlist, positions):
        spat_position = min(positions)
        for position in xrange(spat_position, len(self)):
            GLib.idle_add(self.update_icon, position)

    def on_playback_state_change(self, event_type, player_obj, track):
        position = self.playlist.current_position
        if position < 0 or position >= len(self):
            return
        GLib.idle_add(self.update_icon, position)

    @guiutil.idle_add()   # sync this call to prevent race conditions
    def on_track_tags_changed(self, type, track, tag):
        if not track or not \
            settings.get_option('gui/sync_on_tag_change', True) or not\
            tag in self.columns:
            return
            
        if self._redraw_timer:
            GLib.source_remove(self._redraw_timer)
        self._redraw_queue.append( track )
        self._redraw_timer = GLib.timeout_add(100, self._on_track_tags_changed)
            
    def _on_track_tags_changed(self):
        self._redraw_timer = None
        tracks = {}
        redraw_queue = self._redraw_queue
        self._redraw_queue = []
        for track in redraw_queue:
            tracks[track.get_loc_for_io()] = track
           
        for row in self:
            track = tracks.get( row[0].get_loc_for_io() )
            if track is not None:
                track_data = [providers.get_provider('playlist-columns', name).formatter.format(track) for name in self.columns]
                for i in range(len(track_data)):
                    row[2+i] = track_data[i]

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
        
        # get column types
        coltypes = [self.get_column_type(i) for i in xrange(self.get_n_columns())]
        formatters = [providers.get_provider('playlist-columns', name).formatter.format for name in self.columns]
        self.data_loading = True
        self.emit('data-loading', True)
        
        if len(tracks) > 50:
            self._load_data_thread(coltypes, formatters, tracks)
        else:
            render_data = self._load_data_fn(coltypes, formatters, tracks)
            self._load_data_done(render_data)
    
    @common.threaded
    def _load_data_thread(self, coltypes, formatters, tracks):
        render_data = self._load_data_fn(coltypes, formatters, tracks)
        GLib.idle_add(self._load_data_done, render_data)
    
    def _load_data_fn(self, coltypes, formatters, tracks):
    
        Value = GObject.Value
    
        render_data = []
    
        for position, track in tracks:
            track_data = [track, self.icon_for_row(position).pixbuf] + [formatter(track) for formatter in formatters]
            render_data.append((position, [Value(typ, val) for typ, val in izip(coltypes, track_data)]))
        
        return render_data
        
    def _load_data_done(self, render_data):
        for args in render_data:
            self.insert(*args)
        
        self.data_loading = False
        self.emit('data-loading', False)
        
        if self.data_load_queue:
            tracks = self.data_load_queue
            self.data_load_queue = None
            
            self._load_data(tracks)
