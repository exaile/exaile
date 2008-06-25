# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

import gtk, pango
from xlgui import guiutil
from gettext import gettext as _
from xl import playlist, event

class Column(object):
    __slots__ = ['id', 'display', 'size']
    def __init__(self, id, display, size):
        self.id = id
        self.display = display
        self.size = size
    def __repr__(self):
        return 'Column(%s, %s, %s)' % (`self.id`, `self.display`, `self.size`)

class Playlist(gtk.VBox):
    """
        Represents an xl.playlist.Playlist in the GUI
    """
    COLUMNS = [
        Column('tracknumber', _('#'), 30),
        Column('title', _('Title'), 200),
        Column('artist', _('Artist'), 150),
        Column('album', _('Album'), 150),
        Column('length', _('Length'), 50),
#        Column('disc_id', _('Disc'), 30),
        Column('rating', _('Rating'), 64),
        Column('year', _('Year'), 50),
        Column('genre', _('Genre'), 100),
#        Column('bitrate', _('Bitrate'), 30),
        Column('io_loc', _('Location'), 200),
#        Column('filename', _('Filename'), 200),
#        Column('playcount', _('Playcount'), 50),
    ]

    COLUMN_IDS = []
    column_by_id = {}
    column_by_display = {}
    for col in COLUMNS:
        COLUMN_IDS.append(col.id)
        column_by_id[col.id] = col
        column_by_display[col.display] = col

    default_column_ids = ['tracknumber', 'title', 'album', 'artist', 'length']

    def __init__(self, controller, pl):
        """
            Initializes the playlist

            @param controller:  the main GUI controller
            @param pl: the playlist.Playlist instace to represent
        """
        gtk.VBox.__init__(self)

        self.controller = controller

        self.playlist = pl

        self.settings = controller.exaile.settings

        self._setup_tree()
        self._setup_columns()
        self._set_tracks(self.playlist.get_tracks())

        self.show_all()

        # watch the playlist for changes
        event.add_callback(self.on_add_tracks, 'tracks_added', self)

    def on_add_tracks(self, type, playlist, tracks):
        """
            Called when someone adds tracks to the contained playlist
        """
        for track in tracks:
            self._append_track(track)

    def _set_tracks(self, tracks):
        """
            Sets the tracks that this playlist should display
        """

        self.model.clear()
        self.list.set_model(self.model_blank)

        for track in tracks:
            self._append_track(track)

        self.list.set_model(self.model)

    def _get_ar(self, song):
        """
            Creates the array to be added to the model in the correct order
        """
        ar = [song, None, None]
        for field in self.append_map:
            ar.append(str(song[field]))
        return ar

    def _append_track(self, track):
        """
            Adds a track to this view
        """
        ar = self._get_ar(track)
        self.model.append(ar)

    def get_selected_track(self):
        """
            Returns the currently selected track
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        if not paths: return
        iter = self.model.get_iter(paths[0])
        return model.get_value(iter, 0)

    def on_row_activated(self, *e):
        """
            Called when the user double clicks on a track
        """
        track = self.get_selected_track()
        if not track: return

        index = self.playlist.index(track)
        self.playlist.set_current_pos(index)
        self.controller.exaile.player.stop()
        self.controller.exaile.queue.play()

    def button_press(self, *e):
        """
            stubb
        """
        pass

    def _setup_tree(self):
        """
            Sets up the TreeView for this Playlist
        """
        self.list = guiutil.DragTreeView(self)
        self.list.set_rules_hint(True)
        self.list.set_enable_search(True)
        self.list.connect('row-activated', self.on_row_activated)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.list)
        self.pack_start(self.scroll, True, True)
        self.scroll.show_all()

        selection = self.list.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        
        window = gtk.Window()
        img = window.render_icon('gtk-media-play',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.playimg = img.scale_simple(18, 18,
            gtk.gdk.INTERP_BILINEAR)
        img = window.render_icon('gtk-media-pause',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.pauseimg = img.scale_simple(18, 18,
            gtk.gdk.INTERP_BILINEAR)

    def column_changed(self, *e):
        """
            Called when columns are reordered
        """
        self.list.disconnect(self.changed_id)
        cols = []
        for col in self.list.get_columns():
            cols.append(self.column_by_display[col.get_title()].id)
            self.list.remove_column(col)

        self.settings['gui/col_order'] = cols
        self.setup_columns()

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when data is recieved
        """
        pass

    def setup_model(self, map):
        """
            Gets the array to build the two models
        """
        ar = [object, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf]

        for item in map:
            ar.append(str)

        self.model = gtk.ListStore(*ar)
        self.model_blank = gtk.ListStore(*ar)
        self.list.set_model(self.model)

    def _setup_columns(self):
        """
            Sets up the columns for this table
        """

        self._col_count = 0
        self._length_id = -1

        col_ids = self.settings.get_option("gui/col_order", [])
        search_column = self.settings.get_option("gui/search_column", "Title")
        
        cols = None
        if col_ids:
            cols = []
            for col_id in col_ids[:]:
                col = self.column_by_id.get(col_id)
                if col: # Good entries only
                    cols.append(col)
                else:
                    col_ids.remove(col_id)
        if cols:
            for col in self.COLUMNS:
                if not col in cols:
                    cols.append(col)
                    col_ids.append(col.id)
        else:
            cols = self.COLUMNS[:]
            col_ids = self.COLUMN_IDS[:]

        self.append_map = col_ids
        self.setup_model(col_ids)

        count = 3
        first_col = True
        columns_settings = self.settings.get_option("gui/columns", [])
        if not columns_settings:
            columns_settings = self.default_column_ids

        for col_struct in cols:
            # get cell renderer
            cellr = gtk.CellRendererText()
#            if col_struct.id == 'rating':
#                cellr = gtk.CellRendererPixbuf()
#                cellr.set_property("follow-state", False)

            if col_struct.id in columns_settings:
                if first_col:
                    first_col = False
                    pb = gtk.CellRendererPixbuf()
                    pb.set_fixed_size(20, 20)
                    pb.set_property('xalign', 0.0)
                    stop_pb = gtk.CellRendererPixbuf()
                    stop_pb.set_fixed_size(12, 12)
                    col = gtk.TreeViewColumn(col_struct.display)
                    col.pack_start(pb, False)
                    col.pack_start(stop_pb, False)
                    col.pack_start(cellr, True)
                    col.set_attributes(cellr, text=count)
                    col.set_attributes(pb, pixbuf=1)
                    col.set_attributes(stop_pb, pixbuf=2)
                    col.set_cell_data_func(pb, self.icon_data_func)
                    col.set_cell_data_func(stop_pb, self.stop_icon_data_func)
                else:
                    col = gtk.TreeViewColumn(col_struct.display, cellr, text=count)

                if col_struct.id == 'length':
                    col.set_cell_data_func(cellr, self.length_data_func)
                elif col_struct.id == 'tracknumber':
                    col.set_cell_data_func(cellr, self.track_data_func)
#                elif col_struct.id == 'rating':
#                    col.set_attributes(cellr, pixbuf=1)
#                    col.set_cell_data_func(cellr, self.rating_data_func)
                else:
                    col.set_cell_data_func(cellr, self.default_data_func)

                setting_name = "gui/col_width_%s" % col_struct.id
                width = self.settings.get_option(setting_name, 
                    col_struct.size)
                col.set_fixed_width(width)

                resizable = self.settings.get_option('gui/resizable_cols',
                    False)

                col.connect('clicked', self.set_sort_by)
#                col.connect('notify::width', self.set_column_width)
                col.set_clickable(True)
                col.set_reorderable(True)
                col.set_resizable(False)
                col.set_sort_indicator(False)

                if not resizable:
                    if col_struct.id in ('title', 'artist', 'album', 'io_loc', 'genre'):
                        if col_struct.id != 'genre': 
                            col.set_expand(True)
                            col.set_fixed_width(1)
                        else:
                            col.set_fixed_width(80)
                        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                        cellr.set_property('ellipsize', pango.ELLIPSIZE_END)
                    else:
                        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
                else:
                    col.set_resizable(True)
                    col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)

                if col_struct.id in ('track', 'playcount'):
                    cellr.set_property('xalign', 1.0)
                    
                # Update which column to search for when columns are changed
                if col_struct.display == search_column:
                    self.list.set_search_column(count)
                col.set_widget(gtk.Label(col_struct.display))
                col.get_widget().show()
                self.list.append_column(col)
                col.get_widget().get_ancestor(gtk.Button).connect('button_press_event', 
                    self.press_header)
            count = count + 1
        self.changed_id = self.list.connect('columns-changed', self.column_changed)

    # sort functions courtesy of listen (http://listengnome.free.fr), which
    # are in turn, courtesy of quodlibet.  
    def set_sort_by(self, column):
        """
            Sets the sort column
        """
        title = column.get_title()
        count = 0
        for col in self.list.get_columns():
            if title == col.get_title():
                order = column.get_sort_order()
                if order == gtk.SORT_ASCENDING:
                    order = gtk.SORT_DESCENDING
                else:
                    order = gtk.SORT_ASCENDING
                col.set_sort_indicator(True)
                col.set_sort_order(order)
            else:
                col.set_sort_indicator(False)

        tracks = self.reorder_songs()
        self._set_tracks(tracks)

        curtrack = \
            self.playlist.ordered_tracks[self.playlist.get_current_pos()] 
        self.playlist.ordered_tracks = tracks
        index = self.playlist.index(curtrack)
        self.playlist.set_current_pos(index)

    def reorder_songs(self):
        """
            Resorts all songs
        """
        attr, reverse = self.get_sort_by()

        songs = self.playlist.search('',
            (attr, 'artist', 'album', 'tracknumber', 'title'))

        if reverse:
            songs.reverse()
        return songs

    def get_sort_by(self):
        """
            Gets the sort order
        """
        for col in self.list.get_columns():
            if col.get_sort_indicator():
                return (self.column_by_display[col.get_title()].id,
                    col.get_sort_order() == gtk.SORT_DESCENDING)
        return 'album', False

    def icon_data_func(self, col, cell, model, iter):
        """
            Sets track status (playing/paused/queued) icon
        """

        item = model.get_value(iter, 0)
        image = None

        if item == self.controller.exaile.player.current:
            if self.controller.exaile.player.is_playing():
                image = self.playimg
            elif self.controller.exaile.player.is_paused():
                image = self.pauseimg
#        elif item in self.exaile.player.queued:
#            index = self.exaile.player.queued.index(item)
#            image = xlmisc.get_text_icon(self.exaile.window,
#                str(index + 1), 18, 18)

        cell.set_property('pixbuf', image)

    def stop_icon_data_func(self, col, cell, model, iter):
        """
            Sets "stop after this" icon
        """

        item = model.get_value(iter, 0)
        image = None
       
#        window = gtk.Window()
#        if item == self.controller.exaile.player.stop_track:
#            image = window.render_icon('gtk-stop', 
#                gtk.ICON_SIZE_MENU) 
#            image = image.scale_simple(12, 12, gtk.gdk.INTERP_BILINEAR)
        
        cell.set_property('pixbuf', image)  

    def length_data_func(self, col, cell, model, iter):
        """ 
            Formats the track length
        """
        item = model.get_value(iter, 0)
        try:
            seconds = int(item['length'])
            text = "%s:%02d" % (seconds / 60, seconds % 60)
        except ValueError:
            text = "0:00"
        except:
            text = "0:00"
        cell.set_property('text', text)
        self.set_cell_weight(cell, item)

    def track_data_func(self, col, cell, model, iter):
        """
            Track number
        """
        item = model.get_value(iter, 0)

        track = item.get_track()
        if track == -1:
            cell.set_property('text', '')
        else:
            cell.set_property('text', track)
        self.set_cell_weight(cell, item)
    
    def default_data_func(self, col, cell, model, iter):
        """
            For use in CellRendererTexts that don't have special data funcs.
        """
        item = model.get_value(iter, 0)
        self.set_cell_weight(cell, item)

    def set_cell_weight(self, cell, item):
        """
            Sets a CellRendererText's "weight" property according to whether
            `item` is the currently playing track.
        """
        if item == self.controller.exaile.player.current:
            weight = pango.WEIGHT_HEAVY
        else:
            weight = pango.WEIGHT_NORMAL
        cell.set_property('weight', weight)

    def press_header(self, widget, event):
        pass
#        if event.button != 3:
#            return False
#        menu = self.exaile.xml.get_widget('columns_menu_menu')
#        menu.popup(None, None, None, event.button, event.time)
#        return True

