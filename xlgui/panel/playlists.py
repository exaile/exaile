# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
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

import gtk, urllib, os.path
from xlgui import panel, guiutil, xdg, commondialogs
from xlgui import menu
from xl import playlist
from gettext import gettext as _

class TrackWrapper(object):
    def __init__(self, track, playlist):
        self.track = track
        self.playlist = playlist

    def __str__(self):
        text = self.track['title']
        if text and self.track['artist'] is not None:
            text += " - " + self.track['artist']
        return text

class BasePlaylistPanelMixin(object):
    """
        Base playlist tree object.  

        Used by the radio and playlists panels to display playlists
    """
    def __init__(self):
        """
            Initializes the mixin
        """
        self.playlist_nodes = {}
        self.track_image = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))

    def remove_selected_playlist(self):
        """
            Removes the selected playlist from the UI
            and from the underlying manager
        """
        selected_playlist = self.get_selected_playlist()
        if selected_playlist is not None:
            self.playlist_manager.remove_playlist(
                selected_playlist.get_name())
            #remove from UI
            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            self.model.remove(iter)
        
    def rename_selected_playlist(self, name):
        """
            Renames the selected playlist
            
            @param name: the new name
        """
        pl = self.get_selected_playlist()
        if pl is not None:
            old_name = pl.get_name()
            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            model.set_value(iter, 1, name)
            pl.set_name(name)
            model.set_value(iter, 2, pl)
            #Update the manager aswell
            self.playlist_manager.rename_playlist(old_name, name)
        
    def open_selected_playlist(self):
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.open_playlist(self.tree, model.get_path(iter), None)
        
    def get_selected_playlist(self):
        """
            Retrieves the currently selected playlist in
            the playlists panel.  If a non-playlist is
            selected it returns None
            
            @return: the playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        pl = model.get_value(iter, 2)
        # for smart playlists
        if hasattr(pl, 'get_playlist'):
            return pl.get_playlist()
        elif isinstance(pl, playlist.Playlist) :
            return pl
        else:
            return None
            
    def get_selected_tracks(self):
        """
            Used by the menu, just basically gets the selected
            playlist and returns the tracks in it
        """
        pl = self.get_selected_playlist()
        if pl:
            return pl.get_tracks()
        else:
            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            i = model.get_value(iter, 2)
            if isinstance(i, TrackWrapper):
                return [i.track]

        return None

    def open_playlist(self, tree, path, col):
        """
            Called when the user double clicks on a playlist
        """
        iter = self.model.get_iter(path)
        pl = self.model.get_value(iter, 2)
        if pl is not None:
            # if it's not a playlist, bail
            if not isinstance(pl, (playlist.Playlist,
                playlist.SmartPlaylist)):
                return

            # for smart playlists
            if hasattr(pl, 'get_playlist'):
                pl = pl.get_playlist(self.collection)
    
            self.controller.main.add_playlist(pl)

    def add_new_playlist(self, tracks = []):
        dialog = commondialogs.TextEntryDialog(
                _("Enter the name you want for your new playlist"),
                _("New Playlist"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if not name == "":
                #Create the playlist from all of the tracks
                new_playlist = playlist.Playlist(name)
                new_playlist.add_tracks(tracks)
                self.playlist_nodes[new_playlist] = \
                    self.model.append(self.custom, [self.playlist_image, name,  
                    new_playlist])
                self.tree.expand_row(self.model.get_path(self.custom), False)
                self._load_playlist_nodes(new_playlist)
                # We are adding a completely new playlist with tracks so we save it
                self.playlist_manager.save_playlist(new_playlist)  

    def _load_playlist_nodes(self, playlist):
        """
            Loads the playlist tracks into the node for the specified playlist
        """
        if not playlist in self.playlist_nodes: return

        expanded = self.tree.row_expanded(
            self.model.get_path(self.playlist_nodes[playlist]))

        self._clear_node(self.playlist_nodes[playlist])
        tracks = playlist.ordered_tracks
        for track in tracks:
            wrapper = TrackWrapper(track, playlist)
            self.model.append(self.playlist_nodes[playlist], 
                [self.track_image, str(wrapper), wrapper])

        if expanded:
            self.tree.expand_row(
                self.model.get_path(self.playlist_nodes[playlist]), False)

    def remove_selected_track(self):
        """
            Removes the selected track from its playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        track = model.get_value(iter, 2)
        if isinstance(track, TrackWrapper):
            track.playlist.remove(track.playlist.index(track.track))
            #Update the list
            self.model.remove(iter)
            #TODO do we save the playlist after this??

class PlaylistsPanel(panel.Panel, BasePlaylistPanelMixin):
    """
        The playlists panel
    """
    gladeinfo = ('playlists_panel.glade', 'PlaylistsPanelWindow')

    def __init__(self, controller, playlist_manager, 
        smart_manager, collection):
        """
            Intializes the playlists panel

            @param controller:  The main gui controller
            @param playlist_manager:  The playlist manager
        """
        panel.Panel.__init__(self, controller)
        BasePlaylistPanelMixin.__init__(self)
        self.playlist_manager = playlist_manager
        self.smart_manager = smart_manager
        self.collection = collection
        self.box = self.xml.get_widget('playlists_box')

        self.targets = [('text/uri-list', 0, 0)]

        self.tree = guiutil.DragTreeView(self, True, True)
        self.tree.connect('row-activated', self.open_playlist)
        self.tree.set_headers_visible(False)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(self.scroll, True, True)
        self.box.show_all()

        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)
        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.tree.set_model(self.model)

        # icons
        self.open_folder = guiutil.get_icon('gnome-fs-directory-accept')
        self.playlist_image = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/playlist.png'))

        
        # menus
        self.playlist_menu = menu.PlaylistsPanelPlaylistMenu(self, controller.main)
        self.default_menu = menu.PlaylistsPanelMenu(self)
        self.track_menu  = menu.PlaylistsPanelTrackMenu(self)

        self._load_playlists()

    def _load_playlists(self):
        """
            Loads the currently saved playlists
        """
        self.smart = self.model.append(None, [self.open_folder, 
            _("Smart Playlists"), None])
        
        self.custom = self.model.append(None, [self.open_folder, 
            _("Custom Playlists"), None])

        for name in self.smart_manager.playlists:
            self.model.append(self.smart, [self.playlist_image, name, 
                self.smart_manager.get_playlist(name)])
           
        for name in self.playlist_manager.playlists:
            playlist = self.playlist_manager.get_playlist(name)
            self.playlist_nodes[playlist] = self.model.append(
                self.custom, [self.playlist_image, name, playlist])
            self._load_playlist_nodes(playlist)

        self.tree.expand_row(self.model.get_path(self.smart), False)
        self.tree.expand_row(self.model.get_path(self.custom), False)


    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags some thing onto the playlist panel
        """
        #if the drag originated from playlist view deny it
        #TODO this might change if we are allowed to change the order of playlist
        if tv == context.get_source_widget():
            context.drop_finish(False, etime)
            return  
        
        locs = list(selection.get_uris())
        
        path = self.tree.get_path_at_pos(x, y)
        if path: 
            # Add whatever we received to the playlist at path
            iter = self.model.get_iter(path[0])
            current_playlist = self.model.get_value(iter, 2)
            
            # if the current item is a track, use the parent playlist
            if isinstance(current_playlist, TrackWrapper):
                current_playlist = current_playlist.playlist

            elif not isinstance(current_playlist, playlist.Playlist):
                #Can't add songs to a smart playlists
                context.drop_finish(False, etime)
                return
            (tracks, playlists) = self.tree.get_drag_data(locs)
            current_playlist.add_tracks(tracks)
            self._load_playlist_nodes(current_playlist)
            # Do we save in the case when a user drags a file onto a playlist in the playlist panel?
            # note that the playlist does not have to be open for this to happen
            self.playlist_manager.save_playlist(current_playlist, overwrite=True)
        else:
            # If the user dragged files prompt for a new playlist name
            # else if they dragged a playlist add the playlist
            
            #We don't want the tracks in the playlists to be added to the
            # master tracks list so we pass in False
            (tracks, playlists) = self.tree.get_drag_data(locs, False)
            #First see if they dragged any playlist files
            for new_playlist in playlists:
                self.playlist_nodes[new_playlist] = self.model.append(self.custom, 
                    [self.playlist_image, new_playlist.get_name(), 
                    new_playlist])
                self._load_playlist_nodes(new_playlist)

                # We are adding a completely new playlist with tracks so we save it
                self.playlist_manager.save_playlist(new_playlist, overwrite=True)
                    
            #After processing playlist proceed to ask the user for the 
            #name of the new playlist to add and add the tracks to it
            if len(tracks) > 0:
                self.add_new_playlist(tracks)       
    
    def drag_data_delete(self, *e):
        """
            stub
        """
        pass
    
    def drag_get_data(self, tv, context, selection_data, info, time):
        """
            Called when someone drags something from the playlist
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
        
    def remove_selected_track(self):
        """
            Removes the selected track from its playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        track = model.get_value(iter, 2)
        if isinstance(track, TrackWrapper):
            track.playlist.remove(track.playlist.index(track.track))
            #Update the list
            self.model.remove(iter)
            #TODO do we save the playlist after this??

    def export_selected_playlist(self, path):
        """
            Exports the selected playlist to path
            
            @path where we we want it to be saved, with a 
                valid extension we support
        """
        pl = self.get_selected_playlist()
        if pl is not None:
            playlist.export_playlist(pl, path)
        
    def button_press(self, button, event):
        """
            Called when a button is pressed, is responsible
            for showing the context menu
        """
        if event.button == 3:
            (path, position) = self.tree.get_dest_row_at_pos(int(event.x), int(event.y))
            iter = self.model.get_iter(path)
            pl = self.model.get_value(iter, 2)
            #Based on what is selected determines what
            #menu we will show
            if isinstance(pl, (playlist.Playlist,
                playlist.SmartPlaylist)):
                self.playlist_menu.popup(event)
            elif isinstance(pl, TrackWrapper):
                self.track_menu.popup(event)
            else:
                self.default_menu.popup(event)

    def _clear_node(self, node):
        """
            Clears a node of all children
        """
        iter = self.model.iter_children(node)
        while True:
            if not iter: break
            self.model.remove(iter)
            iter = self.model.iter_children(node)
