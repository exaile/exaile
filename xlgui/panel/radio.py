# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 2, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

import gtk, gobject
from xlgui import panel, guiutil, commondialogs, menu
from xlgui import playlist as guiplaylist
import xlgui.panel.playlists as playlistpanel
from xl import xdg, event, common
from xl import settings
import xl.radio
import threading
import xl.playlist
from xl.nls import gettext as _

class RadioPanel(panel.Panel, playlistpanel.BasePlaylistPanelMixin):
    """
        The Radio Panel
    """
    __gsignals__ = {
        'playlist-selected': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
    }
    gladeinfo = ('radio_panel.glade', 'RadioPanelWindow')

    def __init__(self, parent, collection, 
        radio_manager, station_manager):
        """
            Initializes the radio panel
        """
        panel.Panel.__init__(self, parent)
        playlistpanel.BasePlaylistPanelMixin.__init__(self)
      
        self.collection = collection
        self.manager = radio_manager
        self.playlist_manager = station_manager
        self.nodes = {}
        self.load_nodes = {}
        self.complete_reload = {}

        self._setup_tree()
        self._setup_widgets()
        self._connect_events()
        self.playlist_image = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/playlist.png'))

        # menus
        self.playlist_menu = menu.RadioPanelPlaylistMenu()
        self.track_menu = menu.PlaylistsPanelTrackMenu()

        self.load_streams()

    def load_streams(self):
        """
            Loads radio streams from plugins
        """
        for name in self.playlist_manager.playlists:
            pl = self.playlist_manager.get_playlist(name)
            if pl is not None:
                self.playlist_nodes[pl] = self.model.append(self.custom, 
                    [self.playlist_image,
                    pl.name, pl])
                self._load_playlist_nodes(pl)
        self.tree.expand_row(self.model.get_path(self.custom), False)

        for name, value in self.manager.stations.iteritems():
            self.add_driver(value)

    def _add_driver_cb(self, type, object, driver):
        self.add_driver(driver)

    def add_driver(self, driver):
        """
            Adds a driver to the radio panel
        """
        node = self.model.append(self.radio_root, [self.folder, str(driver), driver])
        self.nodes[driver] = node
        self.load_nodes[driver] = self.model.append(node, [self.refresh_image, 
            _('Loading streams...'), None])
        self.tree.expand_row(self.model.get_path(self.radio_root), False)

        if settings.get_option('gui/radio/%s_station_expanded' % 
                driver.name, False):
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
        pass

    def _connect_events(self):
        """
            Connects events used in this panel
        """
        self.tree.connect('row-expanded', self.on_row_expand)
        self.tree.connect('row-collapsed', self.on_collapsed)
        self.tree.connect('row-activated', self.on_row_activated)

        event.add_callback(self._add_driver_cb, 'station_added', 
                self.manager)
        event.add_callback(self._remove_driver_cb, 'station_removed', 
                self.manager)

    def _setup_tree(self):
        """
            Sets up the tree that displays the radio panel
        """
        box = self.xml.get_widget('RadioPanel')
        self.tree = guiutil.DragTreeView(self, True, True)
        self.tree.set_headers_visible(False)

        self.targets = [('text/uri-list', 0, 0)]

        # columns
        text = gtk.CellRendererText()
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            import pango
            text.set_property( 'ellipsize-set', True)
            text.set_property( 'ellipsize', pango.ELLIPSIZE_END)
        icon = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn('radio')
        col.pack_start(icon, False)
        col.pack_start(text, True)
        col.set_attributes(icon, pixbuf=0)
        col.set_cell_data_func(text, self.cell_data_func)
        self.tree.append_column(col)

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.tree.set_model(self.model)

        self.open_folder = guiutil.get_icon('gnome-fs-directory-accept')
        self.track = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))
        self.folder = guiutil.get_icon('gnome-fs-directory')
        self.refresh_image = guiutil.get_icon('gtk-refresh')

        self.custom = self.model.append(None, [self.open_folder, _("Saved Stations"), None])
        self.radio_root = self.model.append(None, [self.open_folder, _("Radio "
            "Streams"), None])

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        box.pack_start(scroll, True, True)

    def on_row_activated(self, tree, path, column):
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 2)
        if isinstance(item, xl.radio.RadioItem):
            self.emit('playlist-selected', item.get_playlist())
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
        menu = guiutil.Menu()
        menu.append(_("Refresh"), self.on_reload, 'gtk-refresh')
        return menu

    def button_press(self, widget, event):
        """
            Called when someone clicks on the tree
        """
        if event.button == 3:
            (x, y) = map(int, event.get_coords())
            path = self.tree.get_path_at_pos(x, y)
            if path:
                iter = self.model.get_iter(path[0])
                item = self.model.get_value(iter, 2)

                if isinstance(item, (xl.radio.RadioStation, xl.radio.RadioList,
                    xl.radio.RadioItem)):
                    if isinstance(item, xl.radio.RadioStation):
                        station = item
                    else:
                        station = item.station

                    if station and hasattr(station, 'get_menu'):
                        menu = station.get_menu(self)
                        menu.popup(None, None, None, event.button, event.time)
                elif isinstance(item, xl.playlist.Playlist):
                    self.playlist_menu.popup(event)
                elif isinstance(item, playlistpanel.TrackWrapper):
                    self.track_menu.popup(event)

    def cell_data_func(self, column, cell, model, iter):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        cell.set_property('text', str(object))

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags some thing onto the playlist panel
        """
        #if the drag originated from radio view deny it
        #TODO this might change if we are allowed to change the order of radio
        if tv == context.get_source_widget():
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
            current_playlist.add_tracks(tracks)
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
        
        #We don't want the tracks in the playlists to be added to the
        # master tracks list so we pass in False
        (tracks, playlists) = self.tree.get_drag_data(locs, False)
        #First see if they dragged any playlist files
        for new_playlist in playlists:
            self.model.append(self.custom, [self.playlist_image,
                new_playlist.name, new_playlist]) 
            # We are adding a completely new playlist with tracks so we save it
            self.playlist_manager.save_playlist(new_playlist, overwrite=True)
                
        #After processing playlist proceed to ask the user for the 
        #name of the new playlist to add and add the tracks to it
        if len(tracks) > 0:
            dialog = commondialogs.TextEntryDialog(
            _("Enter the name you want for your new playlist"),
            _("New Playlist"))
            result = dialog.run()
            if result == gtk.RESPONSE_OK:
                name = dialog.get_value()
                if not name == "":
                    #Create the playlist from all of the tracks
                    new_playlist = xl.playlist.Playlist(name)
                    new_playlist.add_tracks(tracks)
                    self.playlist_nodes[new_playlist] = self.model.append(self.custom, 
                        [self.playlist_image,
                        new_playlist.name, new_playlist])
                    self.tree.expand_row(self.model.get_path(self.custom), False)
                    # We are adding a completely new playlist with tracks so we save it
                    self.playlist_manager.save_playlist(new_playlist)                
                    self._load_playlist_nodes(new_playlist)

    def drag_get_data(self, tv, context, selection_data, info, time):
        """
            CAlled when the user drags a playlist from the radio panel
        """
        pl = self.get_selected_playlist()
        if pl:
            tracks = pl.get_tracks()
        else:
            tracks = self.get_selected_tracks()
           
        if not tracks: return

        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc()] = track
        
        urls = guiutil.get_urls_for(tracks)
        selection_data.set_uris(urls)
    
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
        if not info: return
        (model, paths) = info
        iter = self.model.get_iter(paths[0])
        object = self.model.get_value(iter, 1)

        if isinstance(object, (xl.radio.RadioList, xl.radio.RadioStation)):
            self._clear_node(iter)
            self.load_nodes[object] = self.model.append(iter,
                [self.refresh_image, _("Loading streams..."), None])

            self.complete_reload[object] = True
            self.tree.expand_row(self.model.get_path(iter), False)

    @staticmethod
    def set_station_expanded_value(station, value):
        settings.set_option(
                'gui/radio/%s_station_expanded' % station,
                True,
                )

    def on_row_expand(self, tree, iter, path):
        """
            Called when a user expands a row in the tree
        """
        driver = self.model.get_value(iter, 2)

        if not isinstance(driver, xl.playlist.Playlist):
            self.model.set_value(iter, 0, self.open_folder)

        if isinstance(driver, xl.radio.RadioStation) or \
            isinstance(driver, xl.radio.RadioList):
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

        no_cache = False
        if driver in self.complete_reload:
            no_cache = True
            del self.complete_reload[driver]

        if isinstance(driver, xl.radio.RadioStation):
            lists = driver.get_lists(no_cache=no_cache)
        else:
            lists = driver.get_items(no_cache=no_cache)

        gobject.idle_add(self._done_loading, iter, driver, lists)

    def _done_loading(self, iter, object, items):
        """
            Called when an item is done loading.  Adds items to the tree
        """
        for item in items:
            if isinstance(item, xl.radio.RadioList): 
                node = self.model.append(self.nodes[object], [self.folder, item.name, item])
                self.nodes[item] = node
                self.load_nodes[item] = self.model.append(node, [self.refresh_image, 
                    _("Loading streams..."), None]) 
            else:
                self.model.append(self.nodes[object], [self.track, item.name,
                    item])

        self.model.remove(self.load_nodes[object])
        del self.load_nodes[object]

    def _clear_node(self, node):
        """
            Clears a node of all children
        """
        iter = self.model.iter_children(node)
        while True:
            if not iter: break
            self.model.remove(iter)
            iter = self.model.iter_children(node)


