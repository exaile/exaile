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
from xlgui import guiutil, menu
from gettext import gettext as _
from xl import playlist, event, track, collection
import copy, urllib
import logging
import os, os.path
logger = logging.getLogger(__name__)

class Column(object):
    def __init__(self, id, display, size):
        self.id = id
        self.display = display
        self.size = size

    def data_func(self, col, cell, model, iter):
        """
            Generic data function
        """
        track = model.get_value(iter, 0)
        value = track[self.id]
        cell.set_property('text', value)
        self.set_cell_weight(cell, value)
    
    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__,
            `self.id`, `self.display`, `self.size`)

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
        Column('discnumber', _('Disc'), 30),
        Column('rating', _('Rating'), 64),
        Column('date', _('Year'), 50),
        Column('genre', _('Genre'), 100),
        Column('bitrate', _('Bitrate'), 30),
        Column('io_loc', _('Location'), 200),
        Column('filename', _('Filename'), 200),
        Column('playcount', _('Playcount'), 50),
    ]

    COLUMN_IDS = []
    column_by_id = {}
    column_by_display = {}
    for col in COLUMNS:
        COLUMN_IDS.append(col.id)
        column_by_id[col.id] = col
        column_by_display[col.display] = col

    default_column_ids = ['tracknumber', 'title', 'album', 'artist', 'length']

    def __init__(self, main, controller, pl):
        """
            Initializes the playlist

            @param controller:  the main GUI controller
            @param pl: the playlist.Playlist instace to represent
        """
        gtk.VBox.__init__(self)

        self.main = main
        self.controller = controller
        self.search_keyword = ''
        self.xml = main.xml

        self.playlist = copy.copy(pl)
        self.playlist.ordered_tracks = pl.ordered_tracks[:]
        self.playlist.current_pos = -1

        self.settings = controller.exaile.settings
        self.col_menus = dict()

        self._setup_tree()
        self._setup_col_menus()
        self._setup_columns()
        self._set_tracks(self.playlist.get_tracks())

        self.menu = menu.PlaylistMenu(self) 

        self.show_all()

        # watch the playlist for changes
        event.add_callback(self.on_add_tracks, 'tracks_added', self.playlist)
        event.add_callback(self.on_remove_tracks, 'tracks_removed',
            self.playlist)

    def _setup_col_menus(self):
        """
            Sets up the column menus (IE, View->Column->Track, etc)
        """
        self.resizable_cols = self.xml.get_widget('col_resizable_item')
        self.not_resizable_cols = \
            self.xml.get_widget('col_not_resizable_item')
        self.resizable_cols.set_active(self.settings.get_option('gui/resizable_cols',
            False))
        self.not_resizable_cols.set_active(not \
            self.settings.get_option('gui/resizable_cols', False))
        self.resizable_cols.connect('activate', self.activate_cols_resizable)
        self.not_resizable_cols.connect('activate',
            self.activate_cols_resizable)

        column_ids = None
        if self.settings.get_option('gui/trackslist_defaults_set', False):
            column_ids = set()
            ids = self.settings.get_option("gui/columns", [])
            # Don't add invalid columns.
            all_ids = frozenset(self.COLUMN_IDS)
            for id in ids:
                if id in all_ids:
                    column_ids.add(id)

        if not column_ids:
            # Use default.
            ids = self.default_column_ids
            self.settings['gui/trackslist_defaults_set'] = True
            self.settings['gui/columns'] = ids
            column_ids = frozenset(ids)


        for col_struct in self.COLUMNS:
            self.col_menus[col_struct.id] = menu = self.xml.get_widget(
                '%s_col' % col_struct.id)

            if menu is None:
                logger.warning("No such column: %s" % col_struct.id)
                continue

            menu.set_active(col_struct.id in column_ids)
            menu.connect('activate', self.change_column_settings,
                ('gui/columns', col_struct))

    def search(self, keyword):
        """
            Filter the playlist with a keyword
        """
        tracks = self.playlist.filter(keyword)
        self._set_tracks(tracks)
        self.search_keyword = keyword

    def change_column_settings(self, item, data):
        """
            Changes column view settings
        """
        pref, col_struct = data
        id = col_struct.id

        column_ids = list(self.settings.get_option(pref, []))
        if item.get_active():
            if id not in column_ids:
                logger.info("adding %s column to %s" % (id, pref))
                column_ids.append(id)
        else:
            if col_struct.id in column_ids:
                logger.info("removing %s column from %s" % (id, pref))
                column_ids.remove(id)
        self.settings[pref] = column_ids

        for i in range(0, self.main.playlist_notebook.get_n_pages()):
            page = self.main.playlist_notebook.get_nth_page(i)
            page.update_col_settings()

    def activate_cols_resizable(self, widget, event=None):
        """
            Called when the user chooses whether or not columns can be
            resizable
        """
        if 'not' in widget.name:
            resizable = False
        else: 
            resizable = True

        self.settings['gui/resizable_cols'] = resizable
        for i in range(0, self.main.playlist_notebook.get_n_pages()):
            page = self.main.playlist_notebook.get_nth_page(i)
            page.update_col_settings()

    def update_col_settings(self):
        """
            Updates the settings for a specific column
        """
        selection = self.list.get_selection()
        info = selection.get_selected_rows()
        
        self.list.disconnect(self.changed_id)
        columns = self.list.get_columns()
        for col in columns:
            self.list.remove_column(col)

        self._setup_columns()
        self._set_tracks(self.playlist.get_tracks())
        self.list.queue_draw()

        if info:
            paths = info[1]
            if paths:
                for path in paths:
                    selection.select_path(path)

    @guiutil.gtkrun
    def on_remove_tracks(self, type, playlist, info):
        """
            Called when someone removes tracks from the contained playlist
        """
        self._set_tracks(playlist.get_tracks())
        self.reorder_songs()
        self.main.update_track_counts()

    @guiutil.gtkrun
    def on_add_tracks(self, type, playlist, tracks):
        """
            Called when someone adds tracks to the contained playlist
        """
        for track in tracks:
            self._append_track(track)
        self.main.update_track_counts()

    def _set_tracks(self, tracks):
        """
            Sets the tracks that this playlist should display
        """

        self.model.clear()
        self.list.set_model(self.model_blank)

        for track in tracks:
            self._append_track(track)

        self.list.set_model(self.model)
        self.main.update_track_counts()

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
        tracks = self.get_selected_tracks()
        if not tracks: return None
        else: return tracks[0]

    def get_selected_tracks(self):
        """
            Gets the selected tracks in the tree view
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        songs = []
        for path in paths:
            iter = self.model.get_iter(path)
            song = self.model.get_value(iter, 0)
            songs.append(song)

        return songs

    def update_iter(self, iter, song):
        """
            Updates the track at "iter"
        """
        ar = self._get_ar(song)
        self.model.insert_after(iter, ar)
        self.model.remove(iter)

    def refresh_row(self, song):
        """
            Refreshes the text for the specified row
        """
        selection = self.list.get_selection()
        model, paths = selection.get_selected_rows()
        iter = self.model.get_iter_first()
        if not iter: return
        while True:
            check = self.model.get_value(iter, 0)
            if not check: break
            if check == song or check.get_loc() == song.get_loc():
                self.update_iter(iter, song)
                break
            iter = self.model.iter_next(iter)
            if not iter: break
      
        if not paths: return
        for path in paths:
            selection.select_path(path)
        self.list.queue_draw()

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

    def button_press(self, button, event):
        """
            Called when the user clicks on the playlist
        """
        if event.button == 3:
            selection = self.list.get_selection()
            self.menu.popup(event)

            if selection.count_selected_rows() <= 1: return False
            else: return True

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
        self._setup_columns()

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when data is recieved
        """
        if self.playlist.ordered_tracks:
            curtrack = self.playlist.get_current()
        else:
            curtrack = None

        #Remove callbacks so they are not fired when we perform actions
        event.remove_callback(self.on_add_tracks, 'tracks_added', self.playlist)
        event.remove_callback(self.on_remove_tracks, 'tracks_removed',
            self.playlist)
        self.list.unset_rows_drag_dest()
        self.list.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            self.list.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        locs = list(selection.get_uris())
        count = 0

        if context.action != gtk.gdk.ACTION_MOVE:
            pass

        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
            if (position == gtk.TREE_VIEW_DROP_BEFORE or
                position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                first = False
            else:
                first = True

        current_tracks = self.playlist.get_tracks()
        for loc in locs:
            loc = loc.replace('file://', '')
            loc = urllib.unquote(loc)

            # If the location we are handling is not in the current collection
            # associated with this playlist then we have to perform extra
            # work to verify if it is a legit file
            c = collection.get_collection_by_loc(loc)
            if c:
                track = c.get_track_by_loc(loc)
            else:
                self.handle_unknown_drag_data(loc)
                continue
            
            if not drop_info:
                self._append_track(track)
            else:
                if not first:
                    first = True
                    ar = self._get_ar(track)
                    if self.model.iter_is_valid(iter):
                        iter = self.model.insert_before(iter, ar)
                    else:
                        iter = self.model.append(ar)
                else:
                    ar = self._get_ar(track)
                    path = self.model.get_path(iter)
                    if self.model.iter_is_valid(iter):
                        iter = self.model.insert_after(iter, ar)
                    else:
                        iter = self.model.append(ar)

        if context.action == gtk.gdk.ACTION_MOVE:
            #On a move action the second True makes the
            # drag_data_delete function called
            context.finish(True, True, etime)
        else:
            context.finish(True, False, etime)

        #iterates through the list and adds any tracks that are
        # not in the playlist to the current playlist
        current_tracks = self.playlist.get_tracks()
        iter = self.model.get_iter_first()
        if not iter: return
        while True:
            track = self.model.get_value(iter, 0)
            if not track in current_tracks: 
                self.playlist.add_tracks((track,))
            iter = self.model.iter_next(iter)
            if not iter: break

        #Re add all of the tracks so that they
        # become ordered 
        iter = self.model.get_iter_first()
        if not iter: return
        self.playlist.ordered_tracks = []
        while True:
            track = self.model.get_value(iter, 0)
            self.playlist.ordered_tracks.append(track)
            iter = self.model.iter_next(iter)
            if not iter: break
    
        # We do not save the playlist because it is saved by the playlist manager?

        event.add_callback(self.on_add_tracks, 'tracks_added', self.playlist)
        event.add_callback(self.on_remove_tracks, 'tracks_removed',
            self.playlist)
        
        if curtrack is not None:
            index = self.playlist.index(curtrack)
            self.playlist.set_current_pos(index)
            
    def drag_data_delete(self, tv, context):
        """
            Called after a drag data operation is complete
            and we want to delete the source data
        """
        if context.drag_drop_succeeded():
            sel = self.list.get_selection()
            (model, paths) = sel.get_selected_rows()
            #Since we want to modify the model we make references to it
            # This allows us to remove rows without it messing up
            rows = []
            for path in paths:
                rows.append(gtk.TreeRowReference(model, path))
            for row in rows:
                iter = self.model.get_iter(row.get_path()) 
                self.model.remove(iter)
            
    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        loc = []
        delete = []
        sel = self.list.get_selection()
        (model, paths) = sel.get_selected_rows()
        for path in paths:
            iter = self.model.get_iter(path)
            song = self.model.get_value(iter, 0) 

            if song.get_type() != 'file':
                guiutil.DragTreeView.dragged_data[song.get_loc()] = song
            loc.append(urllib.quote(str(song.get_loc())))

        selection.set_uris(loc)
        
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
                elif col_struct.id == 'bitrate':
                    col.set_cell_data_func(cellr, self.bitrate_data_func)
                elif col_struct.id == 'tracknumber':
                    col.set_cell_data_func(cellr, self.track_data_func)
#                elif col_struct.id == 'rating':
#                    col.set_attributes(cellr, pixbuf=1)
#                    col.set_cell_data_func(cellr, self.rating_data_func)
                    pass
                else:
                    col.set_cell_data_func(cellr, self.default_data_func)

                setting_name = "gui/col_width_%s" % col_struct.id
                width = self.settings.get_option(setting_name, 
                    col_struct.size)
                col.set_fixed_width(width)

                resizable = self.settings.get_option('gui/resizable_cols',
                    False)

                col.connect('clicked', self.set_sort_by)
                col.connect('notify::width', self.set_column_width)
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

                if col_struct.id in ('tracknumber', 'playcount'):
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

    def set_column_width(self, col, *e):
        """
            Called when the user resizes a column
        """
        col_struct = self.column_by_display[col.get_title()]
        name = 'gui/col_width_%s' % col_struct.id
        self.settings[name] = col.get_width()
        if col_struct.id == 'rating':
            self.rating_width = min(col.get_width(), self.row_height * 4)
            # create_rating_images(self)

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

        if not self.playlist.ordered_tracks: return
        try:
            curtrack = \
                self.playlist.ordered_tracks[self.playlist.get_current_pos()] 
        except IndexError:
            curtrac = self.playlist.ordered_tracks[0]
        self.playlist.ordered_tracks = tracks
        index = self.playlist.index(curtrack)
        self.playlist.set_current_pos(index)

    def reorder_songs(self):
        """
            Resorts all songs
        """
        attr, reverse = self.get_sort_by()

        songs = self.playlist.search(self.search_keyword,
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

        # queued items
        elif item in self.controller.exaile.queue.ordered_tracks:
            index = self.controller.exaile.queue.ordered_tracks.index(item)
            image = guiutil.get_text_icon(self.main.window,
                str(index + 1), 18, 18)

        cell.set_property('pixbuf', image)

    def stop_icon_data_func(self, col, cell, model, iter):
        """
            Sets "stop after this" icon
        """

        item = model.get_value(iter, 0)
        image = None
       
        window = gtk.Window()
        if item == self.controller.exaile.queue.stop_track:
            image = window.render_icon('gtk-stop', 
                gtk.ICON_SIZE_MENU) 
            image = image.scale_simple(12, 12, gtk.gdk.INTERP_BILINEAR)
        
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

    def bitrate_data_func(self, col, cell, model, iter):
        """
            Shows the bitrate
        """
        item = model.get_value(iter, 0)
        cell.set_property('text', item.get_bitrate())
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
        if not self.model.iter_is_valid(iter): return
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
        if event.button != 3:
            return False
        menu = self.xml.get_widget('columns_menu_menu')
        menu.popup(None, None, None, event.button, event.time)
        return True

    def _print_playlist(self, banner = ''):
        """
            Debug - prints the current playlist to stdout
        """
        print banner
        tracks = self.playlist.get_tracks()
        for track in tracks:
            print track.get_loc()
        print '---Done printing playlist'
