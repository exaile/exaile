# Copyright (C) 2010 Aren Olson
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
import os
import random

import glib, gtk, pango

from xl.nls import gettext as _

from xl import (event, player, providers, settings, trax)
from xlgui import guiutil, icons
import playlist_columns, menu as plmenu
from misc import MetadataList
from notebook import SmartNotebook, NotebookPage, NotebookTab


class PlaylistNotebook(SmartNotebook):
    def create_tab_from_playlist(self, playlist):
        """
            Create a tab that will contain the passed-in playlist

            :param playlist: The playlist to create tab from
            :type playlist: :class:`xl.playlist.Playlist`
        """
        page = PlaylistPage(playlist)
        tab = NotebookTab(self, page)
        self.add_tab(tab, page)
        return tab

    def create_new_playlist(self):
        """
            Create a new tab containing a blank playlist. The tab will
            be automatically given a unique name.
        """
        seen = []

        for n in range(self.get_n_pages()):
            page = self.get_nth_page(n)
            name = page.get_name()
            if name.startswith('Playlist '):
                try:
                    val = int(name[9:])
                except:
                    pass
                else:
                    seen.append(val)
        n = 1

        while True:
            if n not in seen:
                break
            n += 1

        pl = Playlist("Playlist %d"%n)

        return self.create_tab_from_playlist(pl)

    def add_default_tab(self):
        return self.create_new_playlist()


# do this in a function to avoid polluting the global namespace
def __create_playlist_tab_context_menu():
    smi = plmenu.simple_menu_item
    sep = plmenu.simple_separator
    items = []
    items.append(smi('new-tab', [], _("New Playlist"), 'tab-new',
        lambda w, o, c: o.tab.notebook.create_new_playlist()))
    items.append(sep('new-tab-sep', ['new-tab']))
    items.append(smi('rename', ['new-tab-sep'], _("Rename"), 'gtk-edit',
        lambda w, o, c: o.tab.start_rename()))
    items.append(smi('clear', ['rename'], _("Clear"), 'gtk-clear',
        lambda w, o, c: o.playlist.clear()))
    items.append(sep('tab-close-sep', ['clear']))
    items.append(smi('tab-close', ['tab-close-sep'], _("Close"), 'gtk-close',
        lambda w, o, c: o.tab.close()))
    for item in items:
        providers.register('playlist-tab-context', item)
__create_playlist_tab_context_menu()


class PlaylistContextMenu(plmenu.ProviderMenu):
    def __init__(self, page):
        """
            :param page: The :class:`PlaylistPage` this menu is
                associated with.
        """
        plmenu.ProviderMenu.__init__(self, 'playlist-context', page)

    def get_parent_context(self):
        context = {}
        context['selected-tracks'] = self._parent.get_selected_items()

        return context

def __create_playlist_context_menu():
    smi = plmenu.simple_menu_item
    sep = plmenu.simple_separator
    items = []
    items.append(smi('append-queue', [], _("Append to Queue"), 'gtk-add',
            lambda w, o, c: player.QUEUE.add_tracks(
            [t[1] for t in c['selected-tracks']])))
    def toggle_spat_cb(widget, playlistpage, context):
        position = context['selected-tracks'][0][0]
        if position != playlistpage.playlist.spat_position:
            playlistpage.playlist.spat_position = position
        else:
            playlistpage.playlist.spat_position = -1
    items.append(smi('toggle-spat', ['append-queue'],
            _("Toggle Stop After This Track"), 'gtk-stop', toggle_spat_cb))
    items.append(plmenu.RatingMenuItem('rating', ['toggle-spat']))
    # TODO: custom playlist item here
    items.append(sep('sep1', ['rating']))
    def remove_tracks_cb(widget, playlistpage, context):
        tracks = context['selected-tracks']
        playlist = playlistpage.playlist
        # If it's all one block, just delete it in one chunk for
        # maximum speed.
        positions = [t[0] for t in tracks]
        if positions == range(positions[0], positions[0]+len(positions)+1):
            del playlist[positions[0]:positions[0]+len(positions)+1]
        else:
            for position, track in tracks[::-1]:
                del playlist[position]
    items.append(smi('remove', ['sep1'], _("Remove"), 'gtk-remove',
        remove_tracks_cb))
    items.append(sep('sep2', ['remove']))
    items.append(smi('properties', ['sep2'], _("Properties"), 'gtk-properties',
        lambda w, o, c: False))
    for item in items:
        providers.register('playlist-context', item)
__create_playlist_context_menu()


class PlaylistPage(gtk.VBox, NotebookPage):
    """
        Displays a playlist and associated controls.
    """
    menu_provider_name = 'playlist-tab-context'
    def __init__(self, playlist):
        """
            :param playlist: The :class:`xl.playlist.Playlist` to display
                in this page.
        """
        gtk.VBox.__init__(self)
        NotebookPage.__init__(self)

        self.playlist = playlist
        self.icon = None

        uifile = os.path.join(os.path.dirname(__file__), "playlist.ui")
        self.builder = gtk.Builder()
        self.builder.add_from_file(uifile)
        plpage = self.builder.get_object("playlist_page")
        for child in plpage.get_children():
            plpage.remove(child)

        self.shuffle_button = self.builder.get_object("shuffle_button")
        self.repeat_button = self.builder.get_object("repeat_button")
        self.dynamic_button = self.builder.get_object("dynamic_button")

        self.builder.connect_signals(self)

        self.plwin = self.builder.get_object("playlist_window")
        self.controls = self.builder.get_object("controls_box")
        self.pack_start(self.plwin, True, True, padding=2)
        self.pack_start(self.controls, False, False, padding=2)

        self.view = PlaylistView(playlist)
        self.plwin.add(self.view)

        event.add_callback(self.on_shuffle_mode_changed,
                "playlist_shuffle_mode_changed", self.playlist)
        event.add_callback(self.on_repeat_mode_changed,
                "playlist_repeat_mode_changed", self.playlist)
        self.view.model.connect('row-changed', self.on_row_changed)

        self.show_all()

    ## NotebookPage API ##

    def get_name(self):
        return self.playlist.name

    def set_name(self, name):
        self.playlist.name = name

    def handle_close(self):
        return True

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
        pass

    def on_search_entry_activate(self, entry):
        pass

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
        if mode == 'disabled':
            button.set_active(False)
        else:
            button.set_active(True)

    def on_shuffle_mode_set(self, widget, mode):
        """
            Callback for the Shuffle mode menu
        """
        self.playlist.shuffle_mode = mode

    def on_shuffle_mode_changed(self, evtype, playlist, mode):
        """
            Updates the UI to reflect changes in the shuffle mode
        """
        if mode == 'disabled':
            self.shuffle_button.set_active(False)
        else:
            self.shuffle_button.set_active(True)

    def on_repeat_mode_set(self, widget, mode):
        """
            Callback for the Repeat mode menu
        """
        self.playlist.repeat_mode = mode

    def on_repeat_mode_changed(self, evtype, playlist, mode):
        """
            Updates the UI to reflect changes in the repeat mode
        """
        if mode == 'disabled':
            self.repeat_button.set_active(False)
        else:
            self.repeat_button.set_active(True)

    def on_row_changed(self, model, path, iter):
        """
            Sets the tab icon to reflect the playback status
        """
        if path[0] == self.playlist.current_position:
            pixbuf = model.get_value(iter, 0)
            if pixbuf == model.clear_pixbuf:
                pixbuf = None
            self.tab.set_icon(pixbuf)


class PlaylistView(gtk.TreeView):
    default_columns = ['tracknumber', 'title', 'album', 'artist', '__length']
    def __init__(self, playlist):
        gtk.TreeView.__init__(self)
        self.playlist = playlist
        self.model = PlaylistModel(playlist, self.default_columns)
        self.menu = PlaylistContextMenu(self)
        self.dragging = False
        self.button_held = False    # used by columns to determine whether
                                    # a notify::width event was initiated
                                    # by the user.

        self.set_rules_hint(True)
        self.set_enable_search(True)
        self.selection = self.get_selection()
        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.set_model(self.model)
        self.columns_changed_id = 0
        self._setup_columns()

        self.targets = [("exaile-index-list", gtk.TARGET_SAME_WIDGET, 0),
                ("text/uri-list", 0, 0)]
        self.drag_source_set(gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT|
                gtk.gdk.ACTION_MOVE)

        event.add_callback(self.on_option_set, "gui_option_set")
        self.connect("row-activated", self.on_row_activated)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)

        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-drop", self.on_drag_drop)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.connect("drag-end", self.on_drag_end)
        self.connect("drag-motion", self.on_drag_motion)

    def set_cell_weight(self, cell, iter):
        """
            Called by columns in playlist_columns to set a CellRendererText's
            weight property for the playing track.
        """
        path = self.model.get_path(iter)
        track = self.model.get_track(path)
        if track == player.PLAYER.current and \
                path[0] == self.playlist.get_current_position() and \
                self.playlist == player.QUEUE.current_playlist:
            weight = pango.WEIGHT_HEAVY
        else:
            weight = pango.WEIGHT_NORMAL
        cell.set_property('weight', weight)

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
        tracks = [(path[0], self.model.get_track(path)) for path in paths]
        return tracks

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

    def _setup_columns(self):
        col_ids = settings.get_option("gui/columns", self.default_columns)
        col_ids = [col for col in col_ids if col in playlist_columns.COLUMNS]
        if not col_ids:
            col_ids = self.default_columns
        self.model.columns = col_ids

        for position, column in enumerate(col_ids):
            position += 1 # offset for pixbuf column
            playlist_column = playlist_columns.COLUMNS[column](self, position)
            self.append_column(playlist_column)

    def on_columns_changed(self, widget):
        columns = [c.id for c in self.get_columns()]
        if columns != settings.get_option('gui/columns', []):
            settings.set_option('gui/columns', columns)

    def on_option_set(self, typ, obj, data):
        if data == "gui/columns":
            glib.idle_add(self._refresh_columns, priority=glib.PRIORITY_DEFAULT)

    def on_row_activated(self, *args):
        try:
            position, track = self.get_selected_items()[0]
        except IndexError:
            return

        self.playlist.set_current_position(position)
        player.QUEUE.play(track=track)
        player.QUEUE.set_current_playlist(self.playlist)

    def on_button_press(self, widget, event):
        self.button_held = True
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        elif event.button == 1:
            selection = self.get_selection()
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
        self.button_held = False
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

    ### DND handlers ###
    ## Source
    def on_drag_begin(self, widget, context):
        # TODO: set drag icon
        self.dragging = True

    def on_drag_data_get(self, widget, context, selection, info, etime):
        if selection.target == "exaile-index-list":
            positions = self.get_selected_paths()
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

    def on_drag_data_received(self, widget, context, x, y, selection,
            info, etime):
        # stop default handler from running
        self.stop_emission('drag-data-received')
        drop_info = self.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            insert_position = path[0]
            if position in (gtk.TREE_VIEW_DROP_AFTER, gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                insert_position += 1
        else:
            insert_position = -1
        if selection.target == "exaile-index-list":
            positions = [int(x) for x in selection.data.split(",")]
            tracks = MetadataList()
            # TODO: this can probably be made more-efficient
            for i in positions:
                tracks.extend(self.playlist[i:i+1])
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks
                for i, position in enumerate(positions[:]):
                    if position >= insert_position:
                        position += len(tracks)
                        positions[i] = position
            else:
                self.playlist.extend(tracks)
            for i in positions[::-1]:
                del self.playlist[i]
        elif selection.target == "text/uri-list":
            uris = selection.get_uris()
            tracks = []
            for u in uris:
                tracks.extend(trax.get_tracks_from_uri(u))
            if insert_position >= 0:
                self.playlist[insert_position:insert_position] = tracks
            else:
                self.playlist.extend(tracks)
        context.finish(True, False, etime)

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

        return True

class PlaylistModel(gtk.GenericTreeModel):
    def __init__(self, playlist, columns):
        gtk.GenericTreeModel.__init__(self)
        self.playlist = playlist
        self.columns = columns

        event.add_callback(self.on_tracks_added,
                "playlist_tracks_added", playlist)
        event.add_callback(self.on_tracks_removed,
                "playlist_tracks_removed", playlist)
        event.add_callback(self.on_current_position_changed,
                "playlist_current_position_changed", playlist)
        event.add_callback(self.on_current_position_changed,
                "playlist_spat_position_changed", playlist)
        event.add_callback(self.on_playback_state_change,
                "playback_track_start")
        event.add_callback(self.on_playback_state_change,
                "playback_track_end")
        event.add_callback(self.on_playback_state_change,
                "playback_player_pause")
        event.add_callback(self.on_playback_state_change,
                "playback_player_resume")

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

    def get_track(self, path):
        """
            Returns the Track object associated with the given path. Raises
            IndexError if there is no such track.
        """
        return self.playlist[path[0]]

    ### API for GenericTreeModel ###

    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY

    def on_get_n_columns(self):
        return len(self.columns)+1

    def on_get_column_type(self, index):
        if index == 0:
            return gtk.gdk.Pixbuf
        else:
            return playlist_columns.COLUMNS[self.columns[index-1]].datatype

    def on_get_iter(self, path):
        rowref = path[0]
        if rowref < len(self.playlist):
            return rowref
        else:
            return None

    def on_get_path(self, rowref):
        return (rowref,)

    def on_get_value(self, rowref, column):
        if column == 0:
            if self.playlist.current_position == rowref and \
                    self.playlist[rowref] == player.PLAYER.current and \
                    self.playlist == player.QUEUE.current_playlist:
                state = player.PLAYER.get_state()
                spat = self.playlist.spat_position == rowref
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
            if self.playlist.spat_position == rowref:
                return self.stop_pixbuf
            return self.clear_pixbuf
        else:
            tagname = self.columns[column-1]
            track = self.playlist[rowref]
            formatter = playlist_columns.FORMATTERS[tagname]
            return formatter.format(track)

    def on_iter_next(self, rowref):
        rowref = rowref+1
        if rowref < len(self.playlist):
            return rowref
        else:
            return None

    def on_iter_children(self, parent):
        if rowref:
            return None
        try:
            return self.playlist[0]
        except IndexError:
            return None

    def on_iter_has_child(self, rowref):
        return False

    def on_iter_n_children(self, rowref):
        if rowref:
            return 0
        return len(self.playlist)

    def on_iter_nth_child(self, parent, n):
        if parent:
            return None
        try:
            return self.playlist[n]
        except IndexError:
            return None

    def on_iter_parent(self, child):
        return None


    ### Event callbacks to keep the model in sync with the playlist ###

    def on_tracks_added(self, event_type, playlist, tracks):
        for position, track in tracks:
            self.row_inserted((position,), self.get_iter((position,)))

    def on_tracks_removed(self, event_type, playlist, tracks):
        tracks.reverse()
        for position, track in tracks:
            self.row_deleted((position,))

    def on_current_position_changed(self, event_type, playlist, positions):
        for position in positions:
            if position < 0:
                continue
            path = (position,)
            try:
                iter = self.get_iter(path)
            except ValueError:
                continue
            self.row_changed(path, iter)

    def on_playback_state_change(self, event_type, player_obj, track):
        path = (self.playlist.current_position,)
        try:
            iter = self.get_iter(path)
        except ValueError:
            return
        self.row_changed(path, iter)


class Playlist(object):
    shuffle_modes = ['disabled', 'track', 'album']
    shuffle_mode_names = [_('Shuffle Off'),
            _('Shuffle Tracks'), _('Shuffle Albums')]
    repeat_modes = ['disabled', 'all', 'track']
    repeat_mode_names = [_('Repeat Off'), _('Repeat All'), _('Repeat One')]
    dynamic_modes = ['disabled', 'enabled']
    dynamic_mode_names = [_('Dynamic Off'), _('Dynamic On')]
    # TODO: how do we document properties/events in sphinx?
    """

        PROPERTIES:
            name: playlist name. read/write.

        EVENTS: (all events are synchronous)
            playlist_tracks_added
                fired: after tracks are added
                data: list of tuples of (index, track)
            playlist_tracks_removed
                fired: after tracks are removed
                data: list of tuples of (index, track)
            playlist_current_position_changed
            playlist_shuffle_mode_changed
            playlist_random_mode_changed
            playlist_dynamic_mode_changed
    """
    save_attrs = ['shuffle_mode', 'repeat_mode', 'dynamic_mode',
            'current_position', 'name']
    __playlist_format_version = [2, 0]
    def __init__(self, name, initial_tracks=[]):
        self.__tracks = MetadataList()
        for track in initial_tracks:
            if not isinstance(track, trax.Track):
                raise ValueError, "Need trax.Track object, got %s" % repr(type(x))
            self.__tracks.append(track)
        self.__shuffle_mode = self.shuffle_modes[0]
        self.__repeat_mode = self.repeat_modes[0]
        self.__dynamic_mode = self.dynamic_modes[0]

        # dirty: any change that would alter the on-disk
        #   representation should set this
        # needs_save: changes to list content should set this.
        #   Determines when the 'unsaved' indicator is shown to the user.
        self.__dirty = False
        self.__needs_save = False
        self.__name = name
        self.__current_position = -1
        self.__spat_position = -1
        self.__shuffle_history_counter = 1 # start positive so we can
                                # just do an if directly on the value

    ### playlist-specific API ###

    def _set_name(self, name):
        self.__name = name
        self.__needs_save = self.__dirty = True
        event.log_event("playlist_name_changed", self, name)

    name = property(lambda self: self.__name, _set_name)
    dirty = property(lambda self: self.__dirty)

    def clear(self):
        del self[:]

    def get_current_position(self):
        return self.__current_position

    def set_current_position(self, position):
        oldposition = self.current_position
        if position != -1:
            self.__tracks.set_meta_key(position, "playlist_current_position", True)
        self.__current_position = position
        if oldposition != -1:
            try:
                self.__tracks.del_meta_key(oldposition, "playlist_current_position")
            except KeyError:
                pass
        self.__dirty = True
        event.log_event("playlist_current_position_changed", self, (position, oldposition))

    current_position = property(get_current_position, set_current_position)

    def get_spat_position(self):
        return self.__spat_position

    def set_spat_position(self, position):
        oldposition = self.spat_position
        self.__tracks.set_meta_key(position, "playlist_spat_position", True)
        self.__spat_position = position
        if oldposition != -1:
            try:
                self.__tracks.del_meta_key(oldposition, "playlist_spat_position")
            except KeyError:
                pass
        self.__dirty = True
        event.log_event("playlist_spat_position_changed", self, (position, oldposition))

    spat_position = property(get_spat_position, set_spat_position)

    def get_current(self):
        if self.current_position == -1:
            return None
        return self.__tracks[self.current_position]

    current = property(get_current)

    def on_tracks_changed(self, *args):
        for idx in xrange(len(self.__tracks)):
            if self.__tracks.get_meta_key(idx, "playlist_current_position"):
                self.__current_position = idx
                break
        else:
            self.__current_position = -1
        for idx in xrange(len(self.__tracks)):
            if self.__tracks.get_meta_key(idx, "playlist_spat_position"):
                self.__spat_position = idx
                break
        else:
            self.__spat_position = -1

    def get_shuffle_history(self):
        return  [ (i, self.__tracks[i]) for i in range(len(self)) if \
                self.__tracks.get_meta_key(i, 'playlist_shuffle_history') ]

    def clear_shuffle_history(self):
        for i in xrange(len(self)):
            try:
                self.__tracks.del_meta_key(i, "playlist_shuffle_history")
            except:
                pass

    def __next_random_track(self, mode="track"):
        """
            Returns a valid next track if shuffle is activated based
            on random_mode
        """
        if mode == "album":
            # TODO: we really need proper album-level operations in
            # xl.trax for this
            try:
                # Try and get the next track on the album
                # NB If the user starts the playlist from the middle
                # of the album some tracks of the album remain off the
                # tracks_history, and the album can be selected again
                # randomly from its first track
                curr = self.current
                t = [ x for i, x in enumerate(self) \
                    if x.get_tag_raw('album') == curr.get_tag_raw('album') \
                    and i > self.current_position ]
                t = trax.sort_tracks(['discnumber', 'tracknumber'], t)
                return self.__tracks.index(t[0]), t[0]

            except IndexError: #Pick a new album
                t = self.get_shuffle_history()
                albums = []
                for i, x in t:
                    if not x.get_tag_raw('album') in albums:
                        albums.append(x.get_tag_raw('album'))

                album = random.choice(albums)
                t = [ x for x in self if x.get_tag_raw('album') == album ]
                t = trax.sort_tracks(['tracknumber'], t)
                return self.__tracks.index(t[0]), t[0]
        else:
            hist = set([ i for i, tr in self.get_shuffle_history() ])
            try:
                return random.choice([ (i, self.__tracks[i]) for i, tr in enumerate(self.__tracks)
                        if i not in hist])
            except IndexError: # no more tracks
                return None, None

    def next(self):
        repeat_mode = self.repeat_mode
        shuffle_mode = self.shuffle_mode
        if self.current_position == self.spat_position and self.current_position != -1:
            self.spat_position = -1
            return None

        if repeat_mode == 'track':
            return self.current
        else:
            next = None
            if shuffle_mode != 'disabled':
                if self.current is not None:
                    self.__tracks.set_meta_key(self.current_position,
                            "playlist_shuffle_history", self.__shuffle_history_counter)
                    self.__shuffle_history_counter += 1
                next_index, next = self.__next_random_track(shuffle_mode)
                if next is not None:
                    self.current_position = next_index
                else:
                    self.clear_shuffle_history()
            else:
                try:
                    next = self[self.current_position+1]
                    self.current_position += 1
                except IndexError:
                    next = None

            if next is None:
                self.current_position = -1
                if repeat_mode == 'all' and len(self) > 0:
                    return self.next()
            else:
                return next

    def prev(self):
        repeat_mode = self.repeat_mode
        shuffle_mode = self.shuffle_mode
        if repeat_mode == 'track':
            return self.current

        if shuffle_mode != 'disabled':
            try:
                prev_index, prev = max(self.get_shuffle_history())
            except IndexError:
                return self.get_current()
            self.__tracks.del_meta_key(prev_index, 'playlist_shuffle_history')
            self.current_position = prev_index
        else:
            position = self.current_position - 1
            if position < 0:
                if repeat_mode == 'all':
                    position = len(self) - 1
                else:
                    position = 0
            self.current_position = position
        return self.get_current()

    ### track advance modes ###
    # This code may look a little overkill, but it's this way to
    # maximize forwards-compatibility. get_ methods will not overwrite
    # currently-set modes which may be from a future version, while set_
    # methods explicitly disallow modes not supported in this version.
    # This ensures that 1) saved modes are never clobbered unless a
    # known mode is to be set, and 2) the values returned in _mode will
    # always be supported in the running version.

    def __get_mode(self, modename):
        mode = getattr(self, "_Playlist__%s_mode"%modename)
        modes = getattr(self, "%s_modes"%modename)
        if mode in modes:
            return mode
        else:
            return modes[0]

    def __set_mode(self, modename, mode):
        modes = getattr(self, "%s_modes"%modename)
        if mode not in modes:
            raise TypeError, "Mode %s is invalid" % mode
        else:
            self.__dirty = True
            setattr(self, "_Playlist__%s_mode"%modename, mode)
            event.log_event("playlist_%s_mode_changed"%modename, self, mode)

    def get_shuffle_mode(self):
        return self.__get_mode("shuffle")

    def set_shuffle_mode(self, mode):
        self.__set_mode("shuffle", mode)
        if mode == 'disabled':
            self.clear_shuffle_history()

    shuffle_mode = property(get_shuffle_mode, set_shuffle_mode)

    def get_repeat_mode(self):
        return self.__get_mode('repeat')

    def set_repeat_mode(self, mode):
        self.__set_mode("repeat", mode)

    repeat_mode = property(get_repeat_mode, set_repeat_mode)

    def get_dynamic_mode(self):
        return self.__get_mode("dynamic")

    def set_dynamic_mode(self, mode):
        self.__set_mode("dynamic", mode)

    dynamic_mode = property(get_dynamic_mode, set_dynamic_mode)

    def randomize(self):
        # TODO: add support for randomizing a subset of the list?
        trs = self[:]
        random.shuffle(trs)
        self[:] = trs


    # TODO[0.4?]: drop our custom disk playlist format in favor of an
    # extended XSPF playlist (using xml namespaces?).

    # TODO: add timeout saving support. 5-10 seconds after last change,
    # perhaps?

    def save_to_location(self, location):
        if os.path.exists(location):
            f = open(location + ".new", "w")
        else:
            f = open(location, "w")
        for track in self.__tracks:
            buffer = track.get_loc_for_io()
            # write track metadata
            meta = {}
            items = ('artist', 'album', 'tracknumber',
                    'title', 'genre', 'date')
            for item in items:
                value = track.get_tag_raw(item)
                if value is not None:
                    meta[item] = value[0]
            buffer += '\t%s\n' % urllib.urlencode(meta)
            try:
                f.write(buffer.encode('utf-8'))
            except UnicodeDecodeError:
                continue

        f.write("EOF\n")
        for item in self.save_attrs:
            val = getattr(self, item)
            try:
                strn = settings.MANAGER._val_to_str(val)
            except ValueError:
                strn = ""

            f.write("%s=%s\n"%(item,strn))
        f.close()
        if os.path.exists(location + ".new"):
            os.remove(location)
            os.rename(location + ".new", location)
        self.__needs_save = self.__dirty = False

    def load_from_location(self, location):
        # note - this is not guaranteed to fire events when it sets
        # attributes. It is intended ONLY for initial setup, not for
        # reloading a playlist inline.
        f = None
        for loc in [location, location+".new"]:
            try:
                f = open(loc, 'r')
                break
            except:
                pass
        if not f:
            return
        locs = []
        while True:
            line = f.readline()
            if line == "EOF\n" or line == "":
                break
            locs.append(line.strip())
        items = {}
        while True:
            line = f.readline()
            if line == "":
                break
            item, strn = line[:-1].split("=",1)
            val = settings.MANAGER._str_to_val(strn)
            items[item] = val

        ver = items.get("__playlist_format_version", [1])
        if ver[0] == 1:
            if items.get("repeat_mode") == "playlist":
                items['repeat_mode'] = "all"
        elif ver[0] > self.__playlist_format_version[0]:
            raise IOError, "Cannot load playlist, unknown format"
        elif ver > self.__playlist_format_version:
            logger.warning("Playlist created on a newer Exaile version, some attributes may not be handled.")
        for item, val in items.iteritems():
            if item in self.save_attrs:
                setattr(self, item, val)
        f.close()

        trs = []

        for loc in locs:
            meta = None
            if loc.find('\t') > -1:
                splitted = loc.split('\t')
                loc = "\t".join(splitted[:-1])
                meta = splitted[-1]

            track = None
            track = trax.Track(uri=loc)

            # readd meta
            if not track: continue
            if not track.is_local() and meta is not None:
                meta = cgi.parse_qs(meta)
                for k, v in meta.iteritems():
                    track.set_tag_raw(k, v[0], notify_changed=False)

            trs.append(track)

        self.__tracks[:] = trs

    ### view API ###

    # how views need to work:
    #   when the following methods are called, they do NOT affect the
    #   underlying order, only the 'apparent' order. HOWEVER, if the
    #   structure is modified when a view is in effect, the view
    #   replaces the current order.

    def reverse(self):
        # reverses current view
        pass

    def sort(self):
        # sorts current view
        pass

    # filter acts like a view method, EXCEPT that when it is active, it
    # is illegal to add or reorder items in the playlist. attempting to do
    # so will raise a <TODO>Exception. Deletion while a filter is active
    # is allowed, however items deleted must be visible under the
    # filter.
    # GUI should disable (grey out, beocme insensitive to DnD, etc.)
    # appropriate actions when these conditions are in effect.

    def filter(self):
        pass


    ### list-like API methods ###
    # parts of this section are taken from
    # http://code.activestate.com/recipes/440656-list-mixin/

    def __len__(self):
        return len(self.__tracks)

    def __contains__(self, track):
        return track in self.__tracks

    def __tuple_from_slice(self, i):
        """
            Get (start, end, step) tuple from slice object.
        """
        (start, end, step) = i.indices(len(self))
        if i.step == None:
            step = 1
        return (start, end, step)

    def __getitem__(self, i):
        return self.__tracks.__getitem__(i)

    def __setitem__(self, i, value):
        oldtracks = self.__getitem__(i)
        removed = MetadataList()
        added = MetadataList()

        if isinstance(i, slice):
            for x in value:
                if not isinstance(x, trax.Track):
                    raise ValueError, "Need trax.Track object, got %s"%repr(type(x))

            (start, end, step) = self.__tuple_from_slice(i)

            if isinstance(value, MetadataList):
                metadata = value.metadata
            else:
                metadata = [None] * len(value)

            if step != 1:
                if len(value) != len(oldtracks):
                    raise ValueError, "Extended slice assignment must match sizes."
            self.__tracks.__setitem__(i, value)
            removed = MetadataList(zip(range(start, end, step), oldtracks),
                    oldtracks.metadata)
            if step == 1:
                end = start + len(value)

            added = MetadataList(zip(range(start, end, step), value), metadata)
        else:
            if not isinstance(value, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks[i] = value
            removed = [(i, oldtracks)]
            added = [(i, value)]

        self.on_tracks_changed()
        event.log_event('playlist_tracks_removed', self, removed)
        event.log_event('playlist_tracks_added', self, added)
        self.__needs_save = self.__dirty = True

    def __delitem__(self, i):
        if isinstance(i, slice):
            (start, end, step) = self.__tuple_from_slice(i)
        oldtracks = self.__getitem__(i)
        self.__tracks.__delitem__(i)
        removed = MetadataList()

        if isinstance(i, slice):
            removed = MetadataList(zip(xrange(start, end, step), oldtracks),
                    oldtracks.metadata)
        else:
            removed = [(i, oldtracks)]

        self.on_tracks_changed()
        event.log_event('playlist_tracks_removed', self, removed)
        self.__needs_save = self.__dirty = True

    def append(self, other):
        self[len(self):len(self)] = [other]

    def extend(self, other):
        self[len(self):len(self)] = other

    def count(self, other):
        return self.__tracks.count(other)

    def index(self, item, start=0, end=None):
        if end is None:
            return self.__tracks.index(item, start)
        else:
            return self.__tracks.index(item, start, end)

