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

from gi.repository import GObject
from gi.repository import Gtk

from xl import trax
from xl.nls import gettext as _
from xlgui import panel
from xlgui.panel import menus
from xlgui.widgets.common import DragTreeView


class FlatPlaylistPanel(panel.Panel):
    """
    Flat playlist panel; represents a single playlist
    """

    __gsignals__ = {
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    ui_info = ('flatplaylist.ui', 'FlatPlaylistPanel')

    def __init__(self, parent, name, label):
        panel.Panel.__init__(self, parent, name, label)

        self.box = self.builder.get_object('FlatPlaylistPanel')
        self.model = Gtk.ListStore(int, str, object)
        self.tracks = []
        self._setup_tree()
        if not hasattr(self.parent, 'do_import'):
            self.builder.get_object("import_button").hide()
        self.menu = menus.TrackPanelMenu(self)
        self._connect_events()

    def _connect_events(self):
        self.builder.connect_signals(
            {
                'on_add_button_clicked': self._on_add_button_clicked,
                'on_import_button_clicked': self._on_import_button_clicked,
            }
        )

    def _on_add_button_clicked(self, *e):
        self.emit('append-items', self.tracks, False)

    def _on_import_button_clicked(self, *e):
        tracks = self.tree.get_selected_tracks()
        if len(tracks) == 0:  # nothing selected, do everything
            tracks = self.tracks
        self.parent.do_import(tracks)

    def _setup_tree(self):
        self.tree = FlatPlaylistDragTreeView(self, False, True)
        selection = self.tree.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        self.tree.set_headers_visible(True)
        self.tree.set_model(self.model)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.box.pack_start(self.scroll, True, True, 0)

        text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('#'))
        col.pack_start(text, False)
        col.set_attributes(text, text=0)
        col.set_fixed_width(50)
        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.tree.append_column(col)

        text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_('Title'))
        col.pack_start(text, True)
        col.set_attributes(text, text=1)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_cell_data_func(text, self._title_data_func)
        self.tree.append_column(col)
        self.box.show_all()

    def _title_data_func(self, col, cell, model, iter, _unused):
        if not model.iter_is_valid(iter):
            return
        item = model.get_value(iter, 2)
        cell.set_property('text', item.get_tag_display("title"))

    def set_playlist(self, playlist):
        self.model.clear()

        self.tracks = tracks = list(playlist)
        for i, track in enumerate(tracks):
            self.model.append([i + 1, track.get_tag_display("title"), track])

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
        tracks = self.tree.get_selected_tracks()
        if not tracks:
            return
        for track in tracks:
            DragTreeView.dragged_data[track.get_loc_for_io()] = track
        uris = trax.util.get_uris_from_tracks(tracks)
        selection.set_uris(uris)


class FlatPlaylistDragTreeView(DragTreeView):
    """
    Custom DragTreeView to retrieve data from playlists
    """

    def get_selected_tracks_count(self):
        """
        Returns the count of selected tracks
        """
        return self.get_selection().count_selected_rows()

    def get_selected_tracks(self):
        """
        Returns the currently selected tracks
        """
        (model, paths) = self.get_selection().get_selected_rows()
        tracks = []

        for path in paths:
            iter = model.get_iter(path)
            track = model.get_value(iter, 2)
            tracks.append(track)

        return tracks
