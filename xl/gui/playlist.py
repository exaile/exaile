# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import os, re, urllib
from gettext import gettext as _, ngettext
import operator
import pygtk
pygtk.require('2.0')
import gtk, pango
from xl import xlmisc, common, library, burn, media
import xl.path
import editor, information

# creates the rating images for the caller
def create_rating_images(caller):
    """
        Called to (re)create the pixmaps used for the Rating column.
    """
    if (caller.rating_width != caller.old_r_w and caller.rating_width != 0):
        caller.rating_images = []
        star_size = caller.rating_width / 4

        star = gtk.gdk.pixbuf_new_from_file_at_size(
            xl.path.get_data('images', 'star.png'), star_size, star_size)

        star_size -= 1

        full_image = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, caller.rating_width, star_size)
        full_image.fill(0xffffff00) # transparent white
        for x in range(0, 4):
            star.copy_area(0, 0, star_size, star_size, full_image, star_size * x, 0)
        caller.rating_images.insert(0, full_image)
        for x in range(7, 0, -1):
            this_image = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, caller.rating_width, star_size)
            this_image.fill(0xffffff00) # transparent white
            full_image.copy_area(0, 0, int(x * star_size / 2.0), star_size, this_image, 0, 0)
            caller.rating_images.insert(0, this_image)
        caller.old_r_w = caller.rating_width

class Column(object):
    __slots__ = ['id', 'display', 'size']
    def __init__(self, id, display, size):
        self.id = id
        self.display = display
        self.size = size
    def __repr__(self):
        return 'Column(%s, %s, %s)' % (`self.id`, `self.display`, `self.size`)

class TracksListCtrl(gtk.VBox):
    """
        Represents the track/playlist table
    """
    rating_images = []
    rating_width = 64   # some default value
    old_r_w = -1
    row_height = 16
    
    COLUMNS = [
        Column('track', _('#'), 30),
        Column('title', _('Title'), 200),
        Column('artist', _('Artist'), 150),
        Column('album', _('Album'), 150),
        Column('length', _('Length'), 50),
        Column('disc_id', _('Disc'), 30),
        Column('rating', _('Rating'), 80),
        Column('year', _('Year'), 50),
        Column('genre', _('Genre'), 100),
        Column('bitrate', _('Bitrate'), 30),
        Column('io_loc', _('Location'), 200),
        Column('filename', _('Filename'), 200),
        Column('playcount', _('Playcount'), 50),
    ]

    column_by_id = {}
    column_by_display = {}
    for col in COLUMNS:
        column_by_id[col.id] = col
        column_by_display[col.display] = col

    defaults = ('track', 'title', 'album', 'artist', 'length')
    default_column_ids = []
    for item in defaults:
        default_column_ids.append(column_by_id[item].display)

    prep = "track"
    type = 'track'

    def __init__(self, exaile, queue=False):
        """
            Expects an exaile instance, the parent window, and whether or not
            this is a queue window.  If it's not a queue window, the track
            popup menu will be initialized.
        """
        gtk.VBox.__init__(self)
        self.exaile = exaile
        self.list = xlmisc.DragTreeView(self)
        self.list.set_rules_hint(True)
        self.list.set_enable_search(False)
        self.songs = library.TrackData()

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.list)
        self.pack_start(self.scroll, True, True)
        self.scroll.show_all()
        selection = self.list.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.playimg = self.exaile.window.render_icon('gtk-media-play',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.playimg = self.playimg.scale_simple(18, 18,
            gtk.gdk.INTERP_BILINEAR)
        self.pauseimg = self.exaile.window.render_icon('gtk-media-pause',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.pauseimg = self.pauseimg.scale_simple(18, 18,
            gtk.gdk.INTERP_BILINEAR)

        self.db = exaile.db
        self.inited = False
        self.queue = queue
        self.playlist = None
        self.tpm = None
        self.plugins_item = None
        self.setup_columns()

        create_rating_images(self)

        self.show()
        
        self.setup_events()


    def close_page(self):
        """
            Called when this page in the notebook is closed
        """
        pass

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when data is recieved
        """
        self.list.unset_rows_drag_dest()
        self.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, 
            self.list.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        loc = list(selection.get_uris())
        counter = 0
 
        if context.action != gtk.gdk.ACTION_MOVE:
            self.exaile.status.set_first(
            _("Scanning and adding tracks to current playlist..."))
        xlmisc.finish()

        # first, check to see if they dropped a folder
        copy = loc[:]
        for l in copy:
            l = urllib.unquote(l)
            if os.path.isdir(l.replace("file://", "")):
                # in this case, it is a folder
                for root, dirs, files in os.walk(l.replace("file://", '')):
                    files.sort()
                    for file in files:
                        (stuff, ext) = os.path.splitext(file)
                        if ext.lower() in media.SUPPORTED_MEDIA:
                            loc.append(urllib.quote(os.path.join(root, file)))

        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
            if (position == gtk.TREE_VIEW_DROP_BEFORE or
                position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                first = False
            else:
                first = True

        for l in loc:
            l = l.replace("file://", "")
            l = urllib.unquote(l)
            m = re.search(r'^device_(\w+)://', l)
            if m:
                song = self.exaile.device_panel.get_song(l)
            else:
                song = library.read_track(self.exaile.db, self.exaile.all_songs, l)
                if not song:
                    # check plugins
                    song = self.get_plugin_track(l)

            if not song: continue
            if song in self.songs:
                # If the song is in drag_delete, we should remove it now
                # so it gets added properly in its new position.  Otherwise,
                # we are adding a track to the playlist that is already there,
                # and should do nothing.
                if song in self.drag_delete:
                    index = self.songs.index(song)
                    itera = self.model.get_iter((index,))
                    self.model.remove(itera)
                    self.songs.remove(song)
                    self.drag_delete.remove(song)
                    self.update_songs()
                else:
                    continue


            if not drop_info:
                # if there's no drop info, just add it to the end
                if song: self.append_song(song)
            else:
                if not first:
                    first = True
                    ar = self.get_ar(song)
                    if self.model.iter_is_valid(iter):
                        iter = self.model.insert_before(iter, ar)
                    else:
                        iter = self.model.append(ar)
                else:
                    ar = self.get_ar(song)
                    path = self.model.get_path(iter)
                    if self.model.iter_is_valid(iter):
                        iter = self.model.insert_after(iter, ar)
                    else:
                        iter = self.model.append(ar)

                if counter >= 20:
                    xlmisc.finish()
                    counter = 0
                else:
                    counter += 1
                    
                # Update here in case multiple tracks are being dragged.
                self.update_songs()
                
            # For some reason songs not in the database will always
            # show up as not in playlist_songs even if it is already there.
            # So instead of just appending if song is in self.playlist_songs, 
            # we compare track.loc to song.loc.  If that's there, we assign
            # song to the already existing track, otherwise, we append the
            # new song like normal.
            found_track = False
            for track in self.playlist_songs:                
                if track.loc == song.loc:
                    song = track
                    found_track = True
            if not found_track:
                self.playlist_songs.append(song)

        # Now that we've inserted new rows for the dragged tracks
        # we need to delete the original rows and track entries.
        if context.action == gtk.gdk.ACTION_MOVE:
            for track in self.drag_delete:
                index = self.songs.index(track)
                iter = self.model.get_iter((index,))
                self.model.remove(iter)
                self.songs.remove(track)
            self.drag_delete = []

        if context.action == gtk.gdk.ACTION_MOVE:
            context.finish(True, True, etime)
        else:
            context.finish(True, False, etime)
        self.update_songs()
        if self.type != 'queue':
            self.exaile.update_songs(self.songs, False)
        self.exaile.status.set_first(None)

    def get_plugin_track(self, loc):
        """
            Checks to see if a track is in the available plugin list
        """
        for k, v in self.exaile.plugin_tracks.iteritems():
            tr = v.for_path(loc)
            if tr: return tr

        return None

    def update_songs(self):
        """
            Updates the songs for the new order
        """
        songs = library.TrackData()
        iter = self.model.get_iter_first()
        if not iter: return
        while True:
            song = self.model.get_value(iter, 0)
            songs.append(song)
            iter = self.model.iter_next(iter)
            if not iter: break

        self.songs = songs

    def ensure_visible(self, track):
        """
            Scrolls to a track
        """
        if not track in self.songs: return
        index = self.songs.index(track)
        path = (index,)
        self.list.scroll_to_cell(path)
        self.list.set_cursor(path)
    
    def get_songs(self):
        """
            Returns the tracks displayed in this list
        """
        return self.songs

    def get_next_track(self, song):
        """
            Gets the next track
        """
        if song is None:
            index = -1
        else: 
            try:
                index = self.songs.index(song)
            except ValueError:
                return None
        path = (index + 1,)
        try:
            iter = self.model.get_iter(path)
        except ValueError:
            return None
        if not iter: return None
        return self.model.get_value(iter, 0)

    def get_previous_track(self, song):
        """
            Gets the previous track
        """
        if not song in self.songs: return None
        index = self.songs.index(song)
        path = (index - 1,)
        try:
            iter = self.model.get_iter(path)
        except ValueError:
            return None
        if not iter: return None
        return self.model.get_value(iter, 0)

    def get_selected_track(self):
        """
            Returns the selected track
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        if not paths: return
        iter = model.get_iter(paths[0])
        return model.get_value(iter, 0)

    def get_selected_tracks(self):
        """
            Gets the selected tracks in the tree view
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        songs = library.TrackData()
        for path in paths:
            iter = self.model.get_iter(path)
            song = self.model.get_value(iter, 0)
            songs.append(song)

        return songs

    def setup_events(self):
        """
            Sets up various events
        """
        if self.type != 'queue':
            self.list.connect('row-activated', lambda *e: self.exaile.player.play())
        self.list.connect('key_release_event', self.key_released)

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

            if song.type == 'device':
                device_name = self.exaile.device_panel.get_driver_name()
                loc.append("device_%s://%s" % (device_name, urllib.quote(str(song.loc))))
            else:
                loc.append(urllib.quote(str(song.loc)))
            delete.append(song)
            
        # We can't remove the tracks in delete until the drag operation is
        # complete, because doing so causes strange dragging behavior.
        # So we just make the list available to the drag_data_recieved 
        # function to make use of.
        self.drag_delete = delete
        selection.set_uris(loc)

    def get_iter(self, song):
        """
            Returns the path for a song
        """
        iter = self.model.get_iter_first()
        while True:
            s = self.model.get_value(iter, 0)
            if s == song: return iter

            iter = self.model.iter_next(iter)
            if not iter: break

        return None

    def key_released(self, widget, event):
        """
            Called when someone presses a key
        """

        selection = self.list.get_selection()
        (model, pathlist) = selection.get_selected_rows()

        # Delete
        if event.keyval == gtk.keysyms.Delete:
            delete = []
            for path in pathlist:
                iter = model.get_iter(path)
                track = model.get_value(iter, 0)
                delete.append(track)

            for track in delete:
                iter = self.get_iter(track)
                model.remove(iter)
                self.songs.remove(track)
                if track in self.playlist_songs:
                    self.playlist_songs.remove(track)

            if pathlist and self.songs:
                path = pathlist[0]
                if path[0] >= len(self.songs): path = (path[0] - 1,)
                selection.select_path(path)
        # Q
        elif event.keyval == gtk.keysyms.q and self.type != 'queue':
            for path in pathlist:
                iter = model.get_iter(path)
                track = model.get_value(iter, 0)
                if not track in self.exaile.player.queued:
                    self.exaile.player.queued.append(track)
                else:
                    self.exaile.player.queued.remove(track)

            update_queued(self.exaile)
            self.queue_draw()

    def setup_model(self, map):
        """
            Gets the array to build the two models
        """
        ar = [object, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf]

        for item in map:
            if item == "track":
                ar.append(int)
            else:
                ar.append(str)

        self.model = gtk.ListStore(*ar)
        self.model_blank = gtk.ListStore(*ar)
        self.list.set_model(self.model)
        self.set_songs(self.songs)

    def setup_columns(self):
        """
            Sets up the columns for this table
        """

        self._col_count = 0
        self._length_id = -1

        col_ids = self.exaile.settings.get_list("ui/col_order", None)
        if col_ids:
            cols = []
            for col_id in col_ids[:]:
                col = self.column_by_id.get(col_id)
                if col: # Good entries only
                    cols.append(col)
                else:
                    col_ids.remove(col_id)
            for col in self.COLUMNS:
                if not col in cols:
                    cols.append(col)
                    col_ids.append(col.id)
        else:
            cols = self.COLUMNS[:]
            col_ids = [col.id for col in cols]

        self.append_map = col_ids
        self.setup_model(col_ids)

        count = 3
        first_col = True
        columns_settings = self.exaile.settings.get_list("ui/%s_columns" % self.prep)

        for col_struct in cols:
            # get cell renderer
            cellr = gtk.CellRendererText()
            if col_struct.id == 'rating':
                cellr = gtk.CellRendererPixbuf()
                cellr.set_property("follow-state", False)

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
                elif col_struct.id == 'track':
                    col.set_cell_data_func(cellr, self.track_data_func)
                elif col_struct.id == 'disc_id':
                    col.set_cell_data_func(cellr, self.disc_data_func)
                elif col_struct.id == 'rating':
                    col.set_attributes(cellr, pixbuf=1)
                    col.set_cell_data_func(cellr, self.rating_data_func)
                else:
                    col.set_cell_data_func(cellr, self.default_data_func)

                setting_name = "ui/%scol_width_%s" % (self.prep, col_struct.id)
                width = self.exaile.settings.get_int(setting_name, 
                    col_struct.size)
                col.set_fixed_width(width)

                resizable = self.exaile.settings.get_boolean('ui/resizable_cols',
                    False)

                if self.type != 'queue':
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

                if col_struct.id in ('track', 'playcount'):
                    cellr.set_property('xalign', 1.0)

                col.set_widget(gtk.Label(col_struct.display))
                col.get_widget().show()
                self.list.append_column(col)
                col.get_widget().get_ancestor(gtk.Button).connect('button_press_event', self.press_header)
            count = count + 1
        self.changed_id = self.list.connect('columns-changed', self.column_changed)
    
    def press_header(self, widget, event):
        if event.button != 3:
            return False
        menu = self.exaile.xml.get_widget('columns_menu_menu')
        menu.popup(None, None, None, event.button, event.time)
        return True

    def header_toggle(self, menuitem, column):
        column.set_visible(not column.get_visible())

    def column_changed(self, *e):
        """
            Called when columns are reordered
        """
        self.list.disconnect(self.changed_id)
        cols = []
        for col in self.list.get_columns():
            cols.append(self.column_by_display[col.get_title()].id)
            self.list.remove_column(col)

        self.exaile.settings['ui/col_order'] = cols
        self.setup_columns()

    def set_column_width(self, col, stuff=None):
        """
            Called when the user resizes a column
        """
        col_struct = self.column_by_display[col.get_title()]
        name = "ui/%scol_width_%s" % (self.prep, col_struct.id)
        self.exaile.settings[name] = col.get_width()
        if col_struct.id == 'rating':
            self.rating_width = min(col.get_width(), self.row_height * 4)
            create_rating_images(self)

    def icon_data_func(self, col, cell, model, iter):
        """
            Sets track status (playing/paused/queued) icon
        """

        item = model.get_value(iter, 0)
        image = None

        if item == self.exaile.player.current:
            if self.exaile.player.is_playing():
                image = self.playimg
            elif self.exaile.player.is_paused():
                image = self.pauseimg
        elif item in self.exaile.player.queued:
            index = self.exaile.player.queued.index(item)
            image = xlmisc.get_text_icon(self.exaile.window,
                str(index + 1), 18, 18)

        cell.set_property('pixbuf', image)

    def stop_icon_data_func(self, col, cell, model, iter):
        """
            Sets "stop after this" icon
        """

        item = model.get_value(iter, 0)
        image = None
        
        if item == self.exaile.player.stop_track:
            image = self.exaile.window.render_icon('gtk-stop', 
                gtk.ICON_SIZE_MENU) 
            image = image.scale_simple(12, 12, gtk.gdk.INTERP_BILINEAR)
        
        cell.set_property('pixbuf', image)  

    def rating_data_func(self, col, cell, model, iter):
        item = model.get_value(iter, 0)
        if not item.rating: return
        idx = len(item.rating) / 2 - 1
        cell.set_property('pixbuf', self.rating_images[idx])

    def set_cell_weight(self, cell, item):
        """
            Sets a CellRendererText's "weight" property according to whether
            `item` is the currently playing track.
        """
        if item == self.exaile.player.current:
            weight = pango.WEIGHT_HEAVY
        else:
            weight = pango.WEIGHT_NORMAL
        cell.set_property('weight', weight)

    def disc_data_func(self, col, cell, model, iter):
        """
            Formats the disc
        """
        item = model.get_value(iter, 0)
        if item.disc_id is None or item.disc_id == -1 or \
            item.type == 'podcast':
            cell.set_property('text', '')
        else:
            cell.set_property('text', item.disc_id)
        self.set_cell_weight(cell, item)

    def filename_data_func(self, col, cell, model, iter):
        """
            Shows the filename of the track
        """
        item = model.get_value(iter, 0)
        cell.set_property('text', os.path.basename(item.io_loc))
        self.set_cell_weight(cell, item)

    def length_data_func(self, col, cell, model, iter):
        """ 
            Formats the track length
        """
        item = model.get_value(iter, 0)
        if item.type == 'podcast':
            text = item.length
        elif item.type == 'stream':
            text = ''
        else:
            seconds = item.duration
            text = "%s:%02d" % (seconds / 60, seconds % 60)
        cell.set_property('text', text)
        self.set_cell_weight(cell, item)

    def track_data_func(self, col, cell, model, iter):
        """
            Track number
        """
        item = model.get_value(iter, 0)
        if item.track is None or item.track == -1 or \
            item.type == 'podcast':
            cell.set_property('text', '')
        else:
            cell.set_property('text', item.track)
        self.set_cell_weight(cell, item)

    def default_data_func(self, col, cell, model, iter):
        """
            For use in CellRendererTexts that don't have special data funcs.
        """
        item = model.get_value(iter, 0)
        self.set_cell_weight(cell, item)

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
                if (not column.get_sort_indicator() or 
                    order == gtk.SORT_DESCENDING):
                    order = gtk.SORT_ASCENDING
                else:
                    order = gtk.SORT_DESCENDING
                col.set_sort_indicator(True)
                col.set_sort_order(order)
            else:
                col.set_sort_indicator(False)

        self.songs = self.reorder_songs(self.songs)
        self.set_songs(self.songs)

    def reorder_songs(self, songs):
        """
            Resorts all songs
        """
        attr, reverse = self.get_sort_by()

        def the_strip(tag):
            return spec_strip(library.the_cutter(tag))
        def spec_strip(tag):
            return library.lstrip_special(tag)

        if attr in ('album', 'title'):
            get_key = lambda track: spec_strip(getattr(track, attr).lower())
        elif attr == 'artist':
            get_key = lambda track: the_strip(track.artist.lower())
        elif attr == 'length':
            get_key = lambda track: track.get_duration()
        else:
            get_key = lambda track: getattr(track, attr)

        s = [
            (get_key(track),
            track)
            for track in songs]

        s  = sorted(s, key=operator.itemgetter(0), reverse=reverse)

        songs = [track[-1] for track in s]
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

    def update_col_settings(self):
        """
            Updates the settings for a specific column
        """
        self.list.disconnect(self.changed_id)
        columns = self.list.get_columns()
        for col in columns:
            self.list.remove_column(col)

#        self.tree_lost_focus(None, None)
        self.setup_columns()
        self.list.queue_draw()

    def set_songs(self, songs, update_playlist=True):
        """
            Sets the songs in this table (expects a list of tracks)
        """
        self.songs = library.TrackData()

        # save sort indicators, because they get reset when you set the model
        indicators = {}
        self.model.clear()
        for col in self.list.get_columns():
            indicators[col.get_title()] = col.get_sort_indicator()

        self.list.set_model(self.model_blank)
        if update_playlist: self.playlist_songs = songs
        for song in songs:
            self.append_song(song)

        self.list.set_model(self.model)
        for col in self.list.get_columns():
            col.set_sort_indicator(indicators[col.get_title()])

    def get_ar(self, song):
        """
            Creates the array to be added to the model in the correct order
        """
        ar = [song, None, None]
        for field in self.append_map:
            ar.append(getattr(song, field))
        return ar

    def append_song(self, song):
        """
            Adds a song to this view
        """
        ar = self.get_ar(song)

        self.model.append(ar)
        if not song in self.songs: self.songs.append(song)

    def update_iter(self, iter, song):
        """
            Updates the track at "iter"
        """
        ar = self.get_ar(song)
        self.model.insert_after(iter, ar)
        self.model.remove(iter)
    
    def update_song_list(self, song, orig_song):
        """
            Updates the in the song list with the new Track object
        """
        index = self.songs.index(orig_song)
        self.songs[index] = song

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
            if check == song or check.io_loc == song.io_loc:
                self.update_iter(iter, song)
                self.update_song_list(song, check)
                break
            iter = self.model.iter_next(iter)
            if not iter: break
      
        if not paths: return
        for path in paths:
            selection.select_path(path)

    def setup_tracks_menu(self):
        """
            Sets up the popup menu for the tracks list
        """
        tpm = xlmisc.Menu()

        # if the menu already exists, remove the plugins menu from it
        if self.plugins_item:
            self.plugins_item.remove_submenu()
            
        self.tpm = tpm        
                
        songs = self.get_selected_tracks()
        t = songs[0].type

        n_selected = len(songs)

        pixbuf = xlmisc.get_text_icon(self.exaile.window, u'\u2610', 16, 16)
        icon_set = gtk.IconSet(pixbuf)
        
        factory = gtk.IconFactory()
        factory.add_default()        
        factory.add('exaile-queue-icon', icon_set)
        
        self.queue = tpm.append(_("Toggle Queue"), self.exaile.on_queue,
            'exaile-queue-icon')

        if n_selected == 1:
            self.stop_track = tpm.append(_("Toggle: Stop after this Track"), 
                self.exaile.on_stop_track, 'gtk-stop')
        tpm.append_separator()

        if t == 'podcast':
            tpm.append(_('Download Podcasts'), self.download_podcast,
            'gtk-save')
        tpm.append(_("Edit Track Information"), lambda e, f:
            editor.TrackEditor(self.exaile, self), 'gtk-edit')

        rm = xlmisc.Menu()
        self.rating_ids = []

        for i in range(0, 8):
            item = rm.append_image(self.rating_images[i],
                lambda w, e, i=i: editor.update_rating(self, i))

        star_icon = gtk.gdk.pixbuf_new_from_file_at_size(
            xl.path.get_data('images', 'star.png'), 16, 16)
        icon_set = gtk.IconSet(star_icon)
        factory = gtk.IconFactory()
        factory.add_default()        
        factory.add('exaile-star-icon', icon_set)

        tpm.append_menu(_("Set Track Rating"), rm, 'exaile-star-icon')

        if t == 'file':
            bm = xlmisc.Menu()
            bm.append(ngettext("Burn Selected Track", "Burn Selected Tracks",
                n_selected), self.burn_selected, 'gtk-cdrom')
            bm.append(_("Burn Playlist"), self.burn_playlist, 'gtk-cdrom')
            tpm.append_menu(_('Burn'), bm, 'gtk-cdrom')
            if not burn.check_burn_progs():
                bm.set_sensitive(False)

        if t == 'cd':
            im = xlmisc.Menu()
            im.append(ngettext("Import Selected Track",
                "Import Selected Tracks", n_selected),
                self.import_selected, 'gtk-cdrom')
            im.append(_('Import CD'), self.import_cd, 'gtk-cdrom')
            tpm.append_menu(_('Import'), im, 'gtk-cdrom')

        if t != 'cd':
            if not songs or not t == 'stream':
                pm = xlmisc.Menu()
                self.new_playlist = pm.append(_("New Playlist"),
                    self.exaile.playlists_panel.on_add_playlist, 'gtk-new')
                pm.append_separator()
                rows = self.db.select("SELECT name FROM playlists WHERE type=0 ORDER BY"
                    " name")
                for row in rows:
                    pm.append(row[0], self.exaile.playlists_panel.add_items_to_playlist)

                tpm.append_menu(_("Add to Playlist"), pm, 'gtk-add')
            else:
                self.playlists_menu = xlmisc.Menu()
                all = self.db.select("SELECT name FROM radio "
                    "ORDER BY name")
                for row in all:
                    i = self.playlists_menu.append(row[0],
                        self.exaile.pradio_panel.add_items_to_station)

                self.playlists_menu.append_separator()
                self.new_playlist = self.playlists_menu.append(_("New Station"),
                    self.exaile.pradio_panel.on_add_to_station, 'gtk-new')

                tpm.append_menu(_("Add to Saved Stations"),
                    self.playlists_menu, 'gtk-add')


        if n_selected == 1:
            info = tpm.append(_("Information"), self.get_track_information,
                'gtk-info')
        tpm.append_separator()

        if n_selected == 1 and self.get_selected_track() \
            and self.get_selected_track().type == 'lastfm':
            lfm = xlmisc.Menu()
            lfm.append('Ban', lambda *e: self.send_lastfm_command('ban'))
            lfm.append('Love', lambda *e: self.send_lastfm_command('love'))
            lfm.append('Skip', lambda *e: self.send_lastfm_command('skip'))
            tpm.append_menu(_("Last.FM Options"), lfm)
            tpm.append_separator()

        factory.add('exaile-track-icon', gtk.IconSet(
            gtk.gdk.pixbuf_new_from_file(xl.path.get_data('images',
            'track.png'))))
        # TRANSLATORS: Shows the selected track in the collection tree
        if n_selected == 1:
            tpm.append(_("Show in Collection"), self.show_in_collection,
                'exaile-track-icon')

        rm = xlmisc.Menu()
        rm.append(_("Remove Selected from Playlist"),
            self.delete_tracks, 'gtk-delete')
        rm.append(_("Blacklist Selected"),
            self.delete_tracks, 'gtk-delete', 'blacklist')
        rm.append(_("Delete Selected"),
            self.delete_tracks, 'gtk-delete', 'delete')

        tpm.append_menu(_("Remove"), rm, 'gtk-delete')

        # plugins menu items
        if self.exaile.plugins_menu.get_children():
            tpm.append_separator()

            # TRANSLATORS: Plugin submenu for the playlist
            self.plugins_item = tpm.append(_("Plugins"), None, 'gtk-execute')
            self.plugins_item.set_submenu(self.exaile.plugins_menu)

    def burn_selected(self, widget, event):
        burn.launch_burner(self.exaile.settings.get_str('burn_prog', burn.check_burn_progs()[0]), \
            self.exaile.tracks.get_selected_tracks())

    def show_in_collection(self, item, event):
        """
            Go to collection tree item corresponding to current track
        """
        track = self.get_selected_track()
        self.exaile.collection_panel.show_in_collection(track)

    def burn_selected(self, widget, event):
        burn.launch_burner(self.exaile.settings.get_str('burn_prog', burn.check_burn_progs()[0]), \
            self.exaile.tracks.get_selected_tracks())

    def burn_playlist(self, widget, event):
        burn.launch_burner(self.exaile.settings.get_str('burn_prog', burn.check_burn_progs()[0]), \
            self.songs)

    def import_selected(self, widget, event):
        self.exaile.importer.do_import(self.get_selected_tracks())

    def import_cd(self, widget, event):
        self.exaile.importer.do_import(self.songs)

    def send_lastfm_command(self, command):
        if self.exaile.player.lastfmsrc:
            self.exaile.player.lastfmsrc.control(command)

    def get_track_information(self, widget, event=None):
        """
            Shows the track information tab
        """
        t = self.get_selected_track()
        information.show_information(self.exaile, t)

    def button_press(self, button, event):
        """
            The popup menu that is displayed when you right click in the
            playlist
        """
        if not event.button == 3: return
        selection = self.list.get_selection()
        self.setup_tracks_menu()

        self.tpm.popup(None, None, None, 0, gtk.get_current_event_time())
        if selection.count_selected_rows() <= 1: return False
        else: return True

    def load(self, genre, plugin):
        """
            Loads the track information from a cache file if it exists.
            If loading it fails, False is returned, else True is returned
        """
        cache = xl.path.get_config('cache')
        if not os.path.isdir(cache): os.mkdir(cache)
        f = "%s%sradioplugin_%s_%s.tab" % (cache, os.sep, plugin, genre)
        if not os.path.isfile(f): return False
        songs = []
        try:
            f = open(f, "r")
            for line in f.readlines():
                line = line.strip()
                fields = line.split("\t")
                info = ({
                    "album": fields[0],
                    "artist": fields[1],
                    "title": fields[2],
                    "loc": fields[3],
                    "bitrate": fields[4].replace("k", "")
                })

                track = media.Track()
                track.set_info(**info)
                track.type = 'stream'
                songs.append(track)
        except:
            xlmisc.log_exception()
            return False
        self.set_songs(songs)
        self.playlist_songs = songs
        return True

    def save(self, genre, plugin):
        """
            Saves the track information to a track file.
        """
        cache = xl.path.get_config('cache')
        if not os.path.isdir(cache): os.mkdir(cache)

        try:
            f = open("%s%sradioplugin_%s_%s.tab" % (cache, os.sep, plugin, genre), "w")
            for track in self.songs:
                f.write("%s\t%s\t%s\t%s\t%s\n" % (track.album, track.artist, track.title,
                    track.loc, track.bitrate))
            f.close()
        except IOError:
            xlmisc.log('Could not save station list')

    def download_podcast(self, event, type):
        """
            Downloads the selected podcasts
        """
        songs = self.get_selected_tracks()
        for song in songs:
            if song.type == 'podcast':
                self.exaile.pradio_panel.add_podcast_to_queue(song)

    def delete_tracks(self, event, type): 
        """
            Deletes tracks, or just removes them from the playlist
        """
        deleting = False
        blacklisting = False
        if type == 'delete': deleting = True
        if type == 'blacklist': blacklisting = True
        delete = []
        delete_confirmed = False

        device_delete = []
        if deleting:
            result = common.yes_no_dialog(self.exaile.window, _("Are you sure "
            "you want to permanently remove the selected tracks from disk?"))
            if result == gtk.RESPONSE_YES: delete_confirmed = True
            else: return
        cur = self.db.cursor()

        error = ""

        if not deleting or delete_confirmed:
            tracks = self.get_selected_tracks()
            
            # stores song before the first selected one so that it can be focused later
            if (self.songs[0] != tracks[0]):
                saved_song_iter = self.get_iter(self.get_previous_track(tracks[0]))
                saved_song_tree_path = self.model.get_path(saved_song_iter)
                scroll = True
            else:
                scroll = False

            
            for track in tracks:
                delete.append(track)

            while len(delete) > 0:
                track = delete.pop()
                path_id = library.get_column_id(self.db, 'paths', 'name', track.loc)
                self.exaile.playlist_songs.remove(track)
                if track == self.exaile.player.stop_track:
                    self.exaile.player.stop_track = None
                try: self.songs.remove(track)
                except ValueError: pass

                # I use exceptions here because the "in" operator takes
                # time that I'm sure has to be repeated in the "remove" method
                # (or at least the "index" method is called, which probably
                # ends up looping until it finds it anyway
                try: self.exaile.songs.remove(track)
                except ValueError: pass

                if deleting or blacklisting:
                    try: self.exaile.all_songs.remove(track)
                    except ValueError: pass

                if deleting:
                    xlmisc.log("Deleting %s" % track.loc)

                    if track.type == 'device':
                        xlmisc.log("Device track detected")
                        device_delete.append(track)
                        continue
                    db = self.db
                    try:
                        if track.type == 'podcast':
                            if track.download_path:
                                os.remove(track.download_path)
                        else:
                            if os.path.isfile(track.loc): 
                                os.remove(track.loc)
                    except OSError:
                        common.error(self.exaile.window, "Could not delete '%s' - "\
                            "perhaps you do not have permissions to do so?"
                            % track.loc)
                    cur.execute("DELETE FROM tracks WHERE path=?", (path_id,))
                else: 
                    # execute if this is "remove from playlist" or "blacklist"
                    playlist = self.playlist
                    if playlist != None:
                        if track.type == 'stream':
                            t = "radio"; p = "url"
                        else:
                            t = "playlists"; p = "path"

                        playlist_id = library.get_column_id(self.db, t, 'name',
                            playlist)

                        if t == 'playlists':
                            t = 'playlist'
                        cur.execute("DELETE FROM %s_items WHERE "
                            "path=? AND %s=?" % (t, t),
                            (path_id, playlist_id))
                    if blacklisting:
                        cur.execute("UPDATE tracks SET blacklisted=1 "
                            "WHERE path=?", (path_id,))

            cur.close()
            if error:
                common.scrolledMessageDialog(self.exaile.window,
                    error, _("The following errors did occur"))
            self.exaile.collection_panel.track_cache = dict()
            self.set_songs(self.songs)
            
            # move to old position
            if scroll:
                self.list.scroll_to_cell(saved_song_tree_path, use_align=True)

            if blacklisting: self.exaile.show_blacklist_manager(False)
            if device_delete:
                self.exaile.device_panel.remove_tracks(device_delete)

class BlacklistedTracksList(TracksListCtrl):
    """
        Shows a list of blacklisted tracks
    """
    blacklist = None
    type = 'blacklist'
    def __init__(self, exaile):
        """
            Initializes the tracks list
        """
        TracksListCtrl.__init__(self, exaile, False)

    def setup_tracks_menu(self):
        """
            Sets up the popup menu for the tracks list
        """
        TracksListCtrl.setup_tracks_menu(self)
        self.deblacklist = self.tpm.append(_("Remove from Blacklist"), 
            self.de_blacklist)

    def de_blacklist(self, item, event):
        """
            Removes items from the blacklist
        """
        songs = self.get_selected_tracks()
        cur = self.db.cursor()
        remove = []
        for track in songs:
            remove.append(track)

        for track in remove:
            self.playlist_songs.remove(track)
            try: self.exaile.songs.remove(track)
            except: pass
            path_id = library.get_column_id(self.db, 'paths', 'name', track.loc)
            cur.execute("UPDATE tracks SET blacklisted=0 WHERE path=?",
                (path_id,)) 
            if not track in self.exaile.all_songs:
                self.exaile.all_songs.append(track)

        self.set_songs(self.exaile.songs)
        self.exaile.collection_panel.track_cache = dict()

class QueueManager(TracksListCtrl):
    """
        Represents all tracks present in the queue
    """
    type = 'queue'
    def __init__(self, exaile):
        """
            Initializes the queue manager
        """
        TracksListCtrl.__init__(self, exaile, True)

        buttons = gtk.HBox()
        buttons.set_border_width(5)
        self.clear = gtk.Button(None)
        self.clear.connect('clicked', self.clear_queue)
        self.clear.set_image(self.image('gtk-clear'))
        buttons.pack_end(self.clear, False, False)
        self.delete = gtk.Button(None)
        self.delete.set_image(self.image('gtk-delete'))
        self.delete.connect('clicked', self.delete_tracks)
        buttons.pack_end(self.delete, False, False)
        self.up = gtk.Button(None)
        self.up.set_image(self.image('gtk-go-up'))
        self.up.connect('clicked', self.move_up)

        buttons.pack_end(self.up, False, False)
        self.down = gtk.Button(None)
        self.down.set_image(self.image('gtk-go-down'))
        self.down.connect('clicked', self.move_down)
        buttons.pack_end(self.down, False, False)
        
        self.pack_start(buttons, False, True)
        buttons.show_all()

        self.set_songs(self.exaile.player.queued)

    def button_press(self, button, event):
        """
            Overridden method of TracksListCtrl.  Does nothing at all
        """
        pass

    def move_down(self, widget):
        """
            Moves the track down in the queue
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()

        try:
            num = paths[0][0]
        except IndexError:
            pass

        iter = model.get_iter(paths[0])

        queue = self.exaile.player.queued
        item = queue.pop(num)
        num += 1
        if num > len(queue):
            num = 0

        queue.insert(num, item)
        self.set_songs(queue)
        selection.select_path((num,))

    def move_up(self, widget):
        """
            Moves the track up in the queue
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        try:
            num = paths[0][0]
        except IndexError:
            pass
        iter = model.get_iter(paths[0])

        queue = self.exaile.player.queued
        item = queue.pop(num)
        num -= 1
        if num < 0:
            num = len(queue)

        queue.insert(num, item)
        self.set_songs(queue)
        selection.select_path((num,))
        
    def delete_tracks(self, item):
        """
            Deletes tracks from the queue
        """
        tracks = self.get_selected_tracks()
        for track in tracks:
            self.exaile.player.queued.remove(track)
            if track == self.exaile.player.stop_track:
                self.exaile.player.stop_track = None

        self.set_songs(self.exaile.player.queued)
        update_queued(self.exaile)

    def clear_queue(self, item):
        """
            Clears the queue
        """
        while self.exaile.player.queued:
            self.exaile.player.queued.pop()

        self.set_songs(self.exaile.player.queued)
        update_queued(self.exaile)

    def image(self, i):
        """
            Returns a stock image
        """
        return gtk.image_new_from_stock(i, gtk.ICON_SIZE_SMALL_TOOLBAR)

    def set_songs(self, songs):
        """
            Sets the tracks for the queue manager, and then disables header
            sorting
        """
        TracksListCtrl.set_songs(self, songs)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Proxy to recieved dragged items.  Calls the parent class, then
            updates the queue order based on the new order of the tracks
        """
        TracksListCtrl.drag_data_received(self, tv, context, x, y, selection, 
            info, etime)
        self.exaile.player.queued = []
        for song in self.songs:
            self.exaile.player.queued.append(song)

        update_queued(self.exaile)

def update_queued(exaile):
    """ 
        If the queue manager is showing, this updates it
    """
    nb = exaile.playlists_nb
    for i in range(0, nb.get_n_pages()):
        page = nb.get_nth_page(i)
        if isinstance(page, QueueManager):
            page.set_songs(exaile.player.queued)

    if exaile.player.queued:
        n = len(exaile.player.queued)
        exaile.queue_count_label.set_label(ngettext(": %d track queued",
            ": %d tracks queued", n) % n)
    else:
        exaile.queue_count_label.set_label("")

