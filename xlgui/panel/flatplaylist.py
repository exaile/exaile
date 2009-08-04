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

from xl.nls import gettext as _
from xlgui import panel, guiutil, menu
from xl import metadata
import gtk, gobject

class FlatPlaylistPanel(panel.Panel):
    """
        Flat playlist panel; represents a single playlist
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
    }

    gladeinfo = ('flatplaylist_panel.glade', 'FlatPlaylistPanelWindow')

    def __init__(self, parent, name=None):
        panel.Panel.__init__(self, parent, name)

        self.box = self.xml.get_widget('FlatPlaylistPanel')
        self.model = gtk.ListStore(int, str, object)
        self.tracks = []
        self._setup_tree()
        self.menu = menu.TrackSelectMenu()
        self._connect_events()

    def _connect_events(self):
        self.xml.signal_autoconnect({
            'on_add_button_clicked': self._on_add_button_clicked,
        })
        self.menu.connect('append-items', lambda *e:
            self.emit('append-items', self.get_selected_tracks()))
        self.menu.connect('queue-items', lambda *e:
            self.emit('queue-items', self.get_selected_tracks()))

    def _on_add_button_clicked(self, *e):
        self.emit('append-items', self.tracks)

    def _setup_tree(self):
        self.tree = guiutil.DragTreeView(self, False, True)
        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.tree.set_headers_visible(True)
        self.tree.set_model(self.model)
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(self.scroll, True, True)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('#'))
        col.pack_start(text, False)
        col.set_attributes(text, text=0)
        col.set_fixed_width(50)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.tree.append_column(col)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Title'))
        col.pack_start(text, True)
        col.set_attributes(text, text=1)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        col.set_cell_data_func(text, self._title_data_func)
        self.tree.append_column(col)
        self.box.show_all()

    def _title_data_func(self, col, cell, model, iter):
        if not model.iter_is_valid(iter): return
        item = model.get_value(iter, 2)
        cell.set_property('text', metadata.j(item['title']))

    def set_playlist(self, pl):
        self.model.clear()

        tracks = pl.get_tracks()
        self.tracks = tracks
        for i, track in enumerate(tracks):
            self.model.append([i + 1, metadata.j(track['title']), track])

    def get_selected_tracks(self):
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()

        tracks = []
        for path in paths:
            iter = self.model.get_iter(path)
            track = self.model.get_value(iter, 2)
            tracks.append(track)

        return tracks

    def button_press(self, button, event):
        """
            Called when the user clicks on the playlist
        """
        if event.button == 3:
            selection = self.tree.get_selection()
            (x, y) = map(int, event.get_coords())
            path = self.tree.get_path_at_pos(x, y)
            self.menu.popup(event)

            if not path:
                return False
            
            if len(self.get_selected_tracks()) >= 2:
                (mods,paths) = selection.get_selected_rows()
                if (path[0] in paths):
                    if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        return False
                    return True
                else:
                    return False
        return False

    def drag_data_received(self, *e):
        """ 
            stub
        """
        pass

    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        tracks = self.get_selected_tracks()
        if not tracks: return
        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc()] = track
        urls = guiutil.get_urls_for(tracks)
        selection.set_uris(urls)

