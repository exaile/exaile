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

import gtk
from xlgui import panel, guiutil, xdg
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

        self.tree = guiutil.DragTreeView(self, True, False)
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

        for name, playlist in self.manager.smart_playlists.iteritems():
            self.model.append(self.smart, [self.playlist_image, name, 
                playlist])

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

    def drag_data_received(self, *e):
        """
            Stubb
        """
        pass
    
    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def button_press(self, *e):
        """
            subb
        """
        pass

