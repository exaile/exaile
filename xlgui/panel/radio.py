# Copyright (C) 2008-2010 Adam Olsen
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
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

import xl.radio
import xl.playlist
from xl import event, common, settings, trax
from xl.nls import gettext as _
import xlgui.panel.playlists as playlistpanel
from xlgui.panel import menus
from xlgui import icons, panel
from xlgui.widgets.common import DragTreeView
from xlgui.widgets import dialogs, menu


class RadioException(Exception):
    pass


class ConnectionException(RadioException):
    pass


class RadioPanel(panel.Panel, playlistpanel.BasePlaylistPanelMixin):
    """
    The Radio Panel
    """

    __gsignals__ = {
        'playlist-selected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }
    __gsignals__.update(playlistpanel.BasePlaylistPanelMixin._gsignals_)

    ui_info = ('radio.ui', 'RadioPanel')
    _radiopanel = None

    def __init__(self, parent, collection, radio_manager, station_manager, name):
        """
        Initializes the radio panel
        """
        panel.Panel.__init__(self, parent, name, _('Radio'))
        playlistpanel.BasePlaylistPanelMixin.__init__(self)

        self.collection = collection
        self.manager = radio_manager
        self.playlist_manager = station_manager
        self.nodes = {}
        self.load_nodes = {}
        self.complete_reload = {}
        self.loaded_nodes = []

        self._setup_tree()
        self._setup_widgets()
        self.playlist_image = icons.MANAGER.pixbuf_from_icon_name(
            'music-library', Gtk.IconSize.SMALL_TOOLBAR
        )

        # menus
        self.playlist_menu = menus.RadioPanelPlaylistMenu(self)
        self.track_menu = menus.TrackPanelMenu(self)
        self._connect_events()

        self.load_streams()
        RadioPanel._radiopanel = self

    @property
    def menu(self):
        """
        Gets a menu for the selected item
        :return: xlgui.widgets.menu.Menu or None if do not have it
        """
        model, it = self.tree.get_selection().get_selected()
        item = model[it][2]
        if isinstance(item, xl.playlist.Playlist):
            return self.playlist_menu
        elif isinstance(item, playlistpanel.TrackWrapper):
            return self.track_menu
        else:
            station = (
                item
                if isinstance(item, xl.radio.RadioStation)
                else item.station
                if isinstance(item, (xl.radio.RadioList, xl.radio.RadioItem))
                else None
            )
            if station and hasattr(station, 'get_menu'):
                return station.get_menu(self)

    def load_streams(self):
        """
        Loads radio streams from plugins
        """
        for name in self.playlist_manager.playlists:
            pl = self.playlist_manager.get_playlist(name)
            if pl is not None:
                self.playlist_nodes[pl] = self.model.append(
                    self.custom, [self.playlist_image, pl.name, pl]
                )
                self._load_playlist_nodes(pl)
        self.tree.expand_row(self.model.get_path(self.custom), False)

        for name, value in self.manager.stations.items():
            self.add_driver(value)

    def _add_driver_cb(self, type, object, driver):
        self.add_driver(driver)

    def add_driver(self, driver):
        """
        Adds a driver to the radio panel
        """
        node = self.model.append(self.radio_root, [self.folder, str(driver), driver])
        self.nodes[driver] = node
        self.load_nodes[driver] = self.model.append(
            node, [self.refresh_image, _('Loading streams...'), None]
        )
        self.tree.expand_row(self.model.get_path(self.radio_root), False)

        if settings.get_option('gui/radio/%s_station_expanded' % driver.name, False):
            self.tree.expand_row(self.model.get_path(node), False)

    def _remove_driver_cb(self, type, object, driver):
        self.remove_driver(driver)

    def remove_driver(self, driver):
        """
        Removes a driver from the radio panel
        """
        if driver in self.nodes:
            self.model.remove(self.nodes[driver])
            del self.nodes[driver]

    def _setup_widgets(self):
        """
        Sets up the various widgets required for this panel
        """
        self.status = self.builder.get_object('status_label')

    @common.idle_add()
    def _set_status(self, message, timeout=0):
        self.status.set_text(message)

        if timeout:
            GLib.timeout_add_seconds(timeout, self._set_status, '', 0)

    def _connect_events(self):
        """
        Connects events used in this panel
        """

        self.builder.connect_signals(
            {'on_add_button_clicked': self._on_add_button_clicked}
        )
        self.tree.connect('row-expanded', self.on_row_expand)
        self.tree.connect('row-collapsed', self.on_collapsed)
        self.tree.connect('row-activated', self.on_row_activated)
        self.tree.connect('key-release-event', self.on_key_released)

        event.add_ui_callback(self._add_driver_cb, 'station_added', self.manager)
        event.add_ui_callback(self._remove_driver_cb, 'station_removed', self.manager)

    def _on_add_button_clicked(self, *e):
        dialog = dialogs.MultiTextEntryDialog(self.parent, _("Add Radio Station"))

        dialog.add_field(_("Name:"))
        url_field = dialog.add_field(_("URL:"))

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()

        if text is not None:
            location = Gio.File.new_for_uri(text)

            if location.get_uri_scheme() is not None:
                url_field.set_text(text)

        result = dialog.run()
        dialog.hide()

        if result == Gtk.ResponseType.OK:
            (name, uri) = dialog.get_values()
            self._do_add_playlist(name, uri)

    @common.threaded
    def _do_add_playlist(self, name, uri):
        from xl import playlist, trax

        if playlist.is_valid_playlist(uri):
            pl = playlist.import_playlist(uri)
            pl.name = name
        else:
            pl = playlist.Playlist(name)
            tracks = trax.get_tracks_from_uri(uri)
            pl.extend(tracks)

        self.playlist_manager.save_playlist(pl)
        self._add_to_tree(pl)

    @common.idle_add()
    def _add_to_tree(self, pl):
        self.playlist_nodes[pl] = self.model.append(
            self.custom, [self.playlist_image, pl.name, pl]
        )
        self._load_playlist_nodes(pl)

    def _setup_tree(self):
        """
        Sets up the tree that displays the radio panel
        """
        box = self.builder.get_object('RadioPanel')
        self.tree = playlistpanel.PlaylistDragTreeView(self, True, True)
        self.tree.set_headers_visible(False)

        self.targets = [Gtk.TargetEntry.new('text/uri-list', 0, 0)]

        # columns
        text = Gtk.CellRendererText()
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            from gi.repository import Pango

            text.set_property('ellipsize-set', True)
            text.set_property('ellipsize', Pango.EllipsizeMode.END)
        icon = Gtk.CellRendererPixbuf()
        col = Gtk.TreeViewColumn('radio')
        col.pack_start(icon, False)
        col.pack_start(text, True)
        col.set_attributes(icon, pixbuf=0)
        col.set_cell_data_func(text, self.cell_data_func)
        self.tree.append_column(col)

        self.model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, object)
        self.tree.set_model(self.model)

        self.track = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.folder = icons.MANAGER.pixbuf_from_icon_name(
            'folder', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.refresh_image = icons.MANAGER.pixbuf_from_icon_name('view-refresh')

        self.custom = self.model.append(None, [self.folder, _("Saved Stations"), None])
        self.radio_root = self.model.append(
            None, [self.folder, _("Radio " "Streams"), None]
        )

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(Gtk.ShadowType.IN)

        box.pack_start(scroll, True, True, 0)

    def on_row_activated(self, tree, path, column):
        item = self.model[path][2]
        if isinstance(item, xl.radio.RadioItem):
            self.emit('playlist-selected', item.get_playlist())
        elif isinstance(item, playlistpanel.TrackWrapper):
            self.emit('playlist-selected', item.playlist)
        elif isinstance(item, xl.playlist.Playlist):
            self.open_station(item)

    def open_station(self, playlist):
        """
        Opens a saved station
        """
        self.emit('playlist-selected', playlist)

    def get_menu(self):
        """
        Returns the menu that all radio stations use
        """
        m = menu.Menu(None)
        m.add_simple(_("Refresh"), self.on_reload, Gtk.STOCK_REFRESH)
        return m

    def on_key_released(self, widget, event):
        """
        Called when a key is released in the tree
        """
        if event.keyval == Gdk.KEY_Menu:
            (mods, paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                iter = self.model.get_iter(paths[0])
                item = self.model.get_value(iter, 2)
                if isinstance(
                    item,
                    (xl.radio.RadioStation, xl.radio.RadioList, xl.radio.RadioItem),
                ):
                    if isinstance(item, xl.radio.RadioStation):
                        station = item
                    else:
                        station = item.station

                    if station and hasattr(station, 'get_menu'):
                        menu = station.get_menu(self)
                        menu.popup(event)
                elif isinstance(item, xl.playlist.Playlist):
                    Gtk.Menu.popup(
                        self.playlist_menu, None, None, None, None, 0, event.time
                    )
                elif isinstance(item, playlistpanel.TrackWrapper):
                    Gtk.Menu.popup(
                        self.track_menu, None, None, None, None, 0, event.time
                    )
            return True

        if event.keyval == Gdk.KEY_Left:
            (mods, paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                self.tree.collapse_row(paths[0])
            return True

        if event.keyval == Gdk.KEY_Right:
            (mods, paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                self.tree.expand_row(paths[0], False)
            return True

        return False

    def cell_data_func(self, column, cell, model, iter, user_data):
        """
        Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        cell.set_property('text', str(object))

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
        Called when someone drags some thing onto the playlist panel
        """
        # if the drag originated from radio view deny it
        # TODO this might change if we are allowed to change the order of radio
        if Gtk.drag_get_source_widget(context) == tv:
            context.drop_finish(False, etime)
            return

        locs = list(selection.get_uris())

        path = self.tree.get_path_at_pos(x, y)
        if path:
            # Add whatever we received to the playlist at path
            iter = self.model.get_iter(path[0])
            current_playlist = self.model.get_value(iter, 2)

            # if it's a track that we've dragged to, get the parent
            if isinstance(current_playlist, playlistpanel.TrackWrapper):
                current_playlist = current_playlist.playlist

            elif not isinstance(current_playlist, xl.playlist.Playlist):
                self._add_new_station(locs)
                return
            (tracks, playlists) = self.tree.get_drag_data(locs)
            current_playlist.extend(tracks)
            # Do we save in the case when a user drags a file onto a playlist in the playlist panel?
            # note that the playlist does not have to be open for this to happen
            self.playlist_manager.save_playlist(current_playlist, overwrite=True)
            self._load_playlist_nodes(current_playlist)
        else:
            self._add_new_station(locs)

    def _add_new_station(self, locs):
        """
        Add a new station
        """
        # If the user dragged files prompt for a new playlist name
        # else if they dragged a playlist add the playlist

        # We don't want the tracks in the playlists to be added to the
        # master tracks list so we pass in False
        (tracks, playlists) = self.tree.get_drag_data(locs, False)
        # First see if they dragged any playlist files
        for new_playlist in playlists:
            self.model.append(
                self.custom, [self.playlist_image, new_playlist.name, new_playlist]
            )
            # We are adding a completely new playlist with tracks so we save it
            self.playlist_manager.save_playlist(new_playlist, overwrite=True)

        # After processing playlist proceed to ask the user for the
        # name of the new playlist to add and add the tracks to it
        if len(tracks) > 0:
            dialog = dialogs.TextEntryDialog(
                _("Enter the name you want for your new playlist"), _("New Playlist")
            )
            result = dialog.run()
            if result == Gtk.ResponseType.OK:
                name = dialog.get_value()
                if not name == "":
                    # Create the playlist from all of the tracks
                    new_playlist = xl.playlist.Playlist(name)
                    new_playlist.extend(tracks)
                    self.playlist_nodes[new_playlist] = self.model.append(
                        self.custom,
                        [self.playlist_image, new_playlist.name, new_playlist],
                    )
                    self.tree.expand_row(self.model.get_path(self.custom), False)
                    # We are adding a completely new playlist with tracks so we save it
                    self.playlist_manager.save_playlist(new_playlist)
                    self._load_playlist_nodes(new_playlist)

    def drag_get_data(self, tv, context, selection_data, info, time):
        """
        Called when the user drags a playlist from the radio panel
        """
        tracks = self.tree.get_selected_tracks()

        if not tracks:
            return

        for track in tracks:
            DragTreeView.dragged_data[track.get_loc_for_io()] = track

        uris = trax.util.get_uris_from_tracks(tracks)
        selection_data.set_uris(uris)

    def drag_data_delete(self, *e):
        """
        stub
        """
        pass

    def on_reload(self, *e):
        """
        Called when the refresh button is clicked
        """
        selection = self.tree.get_selection()
        info = selection.get_selected_rows()
        if not info:
            return
        (model, paths) = info
        iter = self.model.get_iter(paths[0])
        object = self.model.get_value(iter, 2)

        try:
            self.loaded_nodes.remove(self.nodes[object])
        except ValueError:
            pass

        if isinstance(object, (xl.radio.RadioList, xl.radio.RadioStation)):
            self._clear_node(iter)
            self.load_nodes[object] = self.model.append(
                iter, [self.refresh_image, _("Loading streams..."), None]
            )

            self.complete_reload[object] = True
            self.tree.expand_row(self.model.get_path(iter), False)

    @staticmethod
    def set_station_expanded_value(station, value):
        settings.set_option('gui/radio/%s_station_expanded' % station, True)

    def on_row_expand(self, tree, iter, path):
        """
        Called when a user expands a row in the tree
        """
        driver = self.model.get_value(iter, 2)

        if not isinstance(driver, xl.playlist.Playlist):
            self.model.set_value(iter, 0, self.folder)

        if isinstance(driver, xl.radio.RadioStation) or isinstance(
            driver, xl.radio.RadioList
        ):
            if not self.nodes[driver] in self.loaded_nodes:
                self._load_station(iter, driver)

        if isinstance(driver, xl.radio.RadioStation):
            self.set_station_expanded_value(driver.name, True)

    def on_collapsed(self, tree, iter, path):
        """
        Called when someone collapses a tree item
        """
        driver = self.model.get_value(iter, 2)

        if not isinstance(driver, xl.playlist.Playlist):
            self.model.set_value(iter, 0, self.folder)

        if isinstance(driver, xl.radio.RadioStation):
            self.set_station_expanded_value(driver.name, False)

    @common.threaded
    def _load_station(self, iter, driver):
        """
        Loads a radio station
        """
        lists = None
        no_cache = False
        if driver in self.complete_reload:
            no_cache = True
            del self.complete_reload[driver]

        if isinstance(driver, xl.radio.RadioStation):
            try:
                lists = driver.get_lists(no_cache=no_cache)
            except RadioException as e:
                self._set_status(str(e), 2)
        else:
            try:
                lists = driver.get_items(no_cache=no_cache)
            except RadioException as e:
                self._set_status(str(e), 2)

        if not lists:
            return
        GLib.idle_add(self._done_loading, iter, driver, lists)

    def _done_loading(self, iter, object, items):
        """
        Called when an item is done loading.  Adds items to the tree
        """
        self.loaded_nodes.append(self.nodes[object])
        for item in items:
            if isinstance(item, xl.radio.RadioList):
                node = self.model.append(
                    self.nodes[object], [self.folder, item.name, item]
                )
                self.nodes[item] = node
                self.load_nodes[item] = self.model.append(
                    node, [self.refresh_image, _("Loading streams..."), None]
                )
            else:
                self.model.append(self.nodes[object], [self.track, item.name, item])

        try:
            self.model.remove(self.load_nodes[object])
            del self.load_nodes[object]
        except KeyError:
            pass

    def _clear_node(self, node):
        """
        Clears a node of all children
        """
        remove = []
        iter = self.model.iter_children(node)
        while iter:
            remove.append(iter)
            iter = self.model.iter_next(iter)
        for row in remove:
            self.model.remove(row)


def set_status(message, timeout=0):
    RadioPanel._radiopanel._set_status(message, timeout)
