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
from xl import playlist
from gettext import gettext as _

class PlaylistsPanel(panel.Panel):
    """
        The playlists panel
    """
    gladeinfo = ('playlists_panel.glade', 'PlaylistsPanelWindow')

    def __init__(self, controller, playlist_manager):
        """
            Intializes the playlists panel

            @param controller:  The main gui controller
            @param playlist_manager:  The playlist manager
        """
        panel.Panel.__init__(self, controller)
        self.manager = playlist_manager
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
        self.playlist_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/playlist.png'))

        self._load_playlists()

    def _load_playlists(self):
        """
            Loads the currently saved playlists
        """
        self.smart = self.model.append(None, [self.open_folder, 
            _("Smart Playlists"), None])
        
        self.custom = self.model.append(None, [self.open_folder, 
            _("Custom Playlists"), None])

        for name, playlist in self.manager.smart_playlists.iteritems():
            self.model.append(self.smart, [self.playlist_image, name, 
                playlist])
            
        for name in self.manager.playlists:
            self.model.append(self.custom, [self.playlist_image, name, 
                self.manager.get_playlist(name)])

        self.tree.expand_all()

    def open_playlist(self, tree, path, col):
        """
            Called when the user double clicks on a playlist
        """
        iter = self.model.get_iter(path)
        playlist = self.model.get_value(iter, 2)

        # for smart playlists
        if hasattr(playlist, 'get_playlist'):
            playlist = playlist.get_playlist()

        self.controller.main.add_playlist(playlist)

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
            if hasattr(current_playlist, 'get_playlist') or current_playlist == None:
                #Can't add songs to a smart playlists
                context.drop_finish(False, etime)
                return
            (tracks, playlists) = self.tree.get_drag_data(locs)
            current_playlist.add_tracks(tracks)
            # Do we save in the case when a user drags a file onto a playlist in the playlist panel?
            # note that the playlist does not have to be open for this to happen
            self.manager.save_playlist(current_playlist)
        else:
            # If the user dragged files prompt for a new playlist name
            # else if they dragged a playlist add the playlist
            
            #We don't want the tracks in the playlists to be added to the
            # master tracks list so we pass in False
            (tracks, playlists) = self.tree.get_drag_data(locs, False)
            #First see if they dragged any playlist files
            for new_playlist in playlists:
                self.model.append(self.custom, [self.playlist_image, new_playlist.get_name(), 
                                                new_playlist])
                # We are adding a completely new playlist with tracks so we save it
                self.manager.save_playlist(new_playlist)
                    
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
                        new_playlist = playlist.Playlist(name)
                        new_playlist.add_tracks(tracks)
                        self.model.append(self.custom, [self.playlist_image, name, 
                                                       new_playlist])
                        # We are adding a completely new playlist with tracks so we save it
                        self.manager.save_playlist(new_playlist)                
    
    def drag_data_delete(self, *e):
        """
            stub
        """
        pass
    
    def drag_get_data(self, tv, context, selection_data, info, time):
        """
            Called when someone drags something from the playlist
        """
        # Find the currently selected playlist
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        playlist = model.get_value(iter, 2)
        # for smart playlists
        if hasattr(playlist, 'get_playlist'):
            tracks = playlist.get_playlist().get_tracks()
        else:
            tracks = playlist.get_tracks()
        # Put the songs in a list of uris
        track_uris = []
        for track in tracks:
            track_uris.append(track.get_loc_for_io())
        selection_data.set_uris(track_uris)

    def button_press(self, *e):
        """
            subb
        """
        pass

