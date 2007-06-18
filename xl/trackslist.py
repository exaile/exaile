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

import sys, os, re, random, fileinput, media
import xlmisc, common, track, tracks, burn 
import copy, time, urllib, xl.tracks
from gettext import gettext as _, ngettext
import pygtk
pygtk.require('2.0')
import gtk, pango

# creates the rating images for the caller
def create_rating_images(caller):
    """
        Called to (re)create the pixmaps used for the Rating column.
    """
    if (caller.rating_width != caller.old_r_w and caller.rating_width != 0):
        caller.rating_images = []
        star_size = caller.rating_width / 4
        star = gtk.gdk.pixbuf_new_from_file_at_size("images/star.png", star_size, star_size)
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

class TracksListCtrl(gtk.VBox):
    """
        Represents the track/playlist table
    """
    rating_images = []
    rating_width = 64   # some default value
    old_r_w = -1
    row_height = 16
    
    default_columns = ('#', _('Title'), _('Album'), _('Artist'), _('Length'))
    col_items = ["#",
        _("Title"), _("Artist"), _("Album"), _("Length"), _("Disc"),
        _("Rating"), _("Year"), _("Genre"), _("Bitrate"), _("Location"),
        _("Filename")]
    col_map = {
        '#': 'track',
        _('Title'): 'title',
        _('Artist'): 'artist',
        _('Album'): 'album',
        _('Length'): 'length',
        _('Disc'): 'disc_id',
        _('Rating'): 'rating',
        _('Year'): 'year',
        _('Genre'): 'genre',
        _('Bitrate'): 'bitrate',
        _('Location'): 'io_loc',
        _('Filename'): 'filename'
        }
    size_map = {
        '#': 30,
        _('Title'): 200,
        _('Artist'): 150,
        _('Album'): 150,
        _('Length'): 50,
        _('Disc'): 30,
        _('Rating'): 80,
        _('Year'): 50,
        _('Genre'): 100,
        _('Bitrate'): 30,
        _('Location'): 100,
        _('Filename'): 50
    }

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
        self.songs = tracks.TrackData()

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

        model = tv.get_model()
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
                    for file in files:
                        (stuff, ext) = os.path.splitext(file)
                        if ext.lower() in media.SUPPORTED_MEDIA:
                            loc.append(urllib.quote(os.path.join(root, file)))

        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = model.get_iter(path)
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
                song = tracks.read_track(self.exaile.db, self.exaile.all_songs, l)
                if not song:
                    # check plugins
                    song = self.get_plugin_track(l)

            if not song or song in self.songs: continue

            if not drop_info:
                # if there's no drop info, just add it to the end
                if song: self.append_song(song)
            else:
                if not first:
                    first = True
                    ar = self.get_ar(song)
                    iter = self.model.insert_before(iter, ar)
                else:
                    ar = self.get_ar(song)
                    iter = self.model.insert_after(iter, ar)
                if counter >= 20:
                    xlmisc.finish()
                    counter = 0
                else:
                    counter += 1
            if not song in self.playlist_songs:
                self.playlist_songs.append(song)

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
        songs = tracks.TrackData()
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
    
    def get_songs(self):
        """
            Returns the tracks displayed in this list
        """
        return self.songs

    def get_next_track(self, song):
        """
            Gets the next track
        """
        if song == None:
            index = -1
        else: 
            if not song in self.songs: return None
	    index = self.songs.index(song)
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
        songs = tracks.TrackData()
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
            self.list.connect('row-activated', self.exaile.play)
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
            
        if context.action == gtk.gdk.ACTION_MOVE:
            for song in delete:
                index = self.songs.index(song)
                iter = self.model.get_iter((index,))
                self.model.remove(iter)
                self.songs.remove(song)

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

        # delete key
        if event.keyval == 65535:
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
        elif event.keyval == 113 and self.type != 'queue': # the 'q' key
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
        cols = self.exaile.settings.get_list("ui/col_order", self.col_items)
        for col in self.col_items:
            if not col in cols:
                cols.append(col)

        self.append_map = [self.col_map[col] for col in cols if col]

        self.setup_model(self.append_map)

        count = 3
        first_col = True
        columns_settings = self.exaile.settings.get_list("ui/%s_columns" % (self.prep,))

        for name in cols:
            if not self.size_map.has_key(name): continue
            # get cell renderer
            cellr = gtk.CellRendererText()
            if _(name) == _("Rating"):
                cellr = gtk.CellRendererPixbuf()
                cellr.set_property("follow-state", False)
            mapval = self.col_map
            
            show = False
            if name in columns_settings:
                show = True

            if show:
                if first_col:
                    first_col = False
                    pb = gtk.CellRendererPixbuf()
                    pb.set_fixed_size(20, 20)
                    pb.set_property('xalign', 0.0)
                    stop_pb = gtk.CellRendererPixbuf()
                    stop_pb.set_fixed_size(12, 12)
                    col = gtk.TreeViewColumn(_(name))
                    col.pack_start(pb, False)
                    col.pack_start(stop_pb, False)
                    col.pack_start(cellr, True)
                    col.set_attributes(cellr, text=count)
                    col.set_attributes(pb, pixbuf=1)
                    col.set_attributes(stop_pb, pixbuf=2)
                    col.set_cell_data_func(pb, self.icon_data_func)
                    col.set_cell_data_func(stop_pb, self.stop_icon_data_func)
                else:
                    col = gtk.TreeViewColumn(_(name), cellr, text=count)
                
                if _(name) == _("Length"):
                    col.set_cell_data_func(cellr, self.length_data_func)
                elif _(name) == "#":
                    col.set_cell_data_func(cellr, self.track_data_func)
                elif _(name) == _('Disc'):
                    col.set_cell_data_func(cellr, self.disc_data_func)
                elif _(name) == _("Rating"):
                    col.set_attributes(cellr, pixbuf=1)
                    col.set_cell_data_func(cellr, self.rating_data_func)

                setting_name = "ui/%scol_width_%s" % (self.prep, name)
                width = self.exaile.settings.get_int(setting_name, 
                    self.size_map[name])
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
                    if _(name) in (_("Title"), _("Artist"), _("Album"), _("Location")):
                        col.set_expand(True)
                        col.set_fixed_width(1)
                        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                        cellr.set_property('ellipsize', pango.ELLIPSIZE_END)
                    else:
                        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
                else:
                    col.set_resizable(True)
                    col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)

                self.list.append_column(col)
            count = count + 1
        self.changed_id = self.list.connect('columns-changed', self.column_changed)

    def column_changed(self, *e):
        """
            Called when columns are reordered
        """
        self.list.disconnect(self.changed_id)
        cols = []
        for col in self.list.get_columns():
            cols.append(col.get_title())
            self.list.remove_column(col)

        self.exaile.settings['ui/col_order'] = cols
        self.setup_columns()

    def set_column_width(self, col, stuff=None):
        """
            Called when the user resizes a column
        """
        name = "ui/%scol_width_%s" % (self.prep, col.get_title())
        self.exaile.settings[name] = col.get_width()
        if col.get_title() == _("Rating"):
            self.rating_width = min(col.get_width(), self.row_height * 4)
            create_rating_images(self)

    def disc_data_func(self, col, cell, model, iter):
        """
            formats the disc
        """
        item = model.get_value(iter, 0)
        if item.disc_id is None or item.disc_id == -1 or \
            item.type == 'podcast':
            cell.set_property('text', '')
        else:
            cell.set_property('text', item.disc_id)

    def filename_data_func(self, col, cell, model, iter):
        """
            Shows the filename of the track
        """
        item = model.get_value(iter, 0)
        cell.set_property('text', os.path.basename(item.io_loc))

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

    # sort functions courtesy of listen (http://listengnome.free.fr), which
    # are in turn, courtesy of quodlibet.  
    def set_sort_by(self, column):
        """
            Sets the sort column
        """
        title = column.get_title()
        count = 0
        for col in self.list.get_columns():
            if column.get_title() == col.get_title():
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

        self.reorder_songs()

    def reorder_songs(self):
        """
            Resorts all songs
        """
        attr, reverse = self.get_sort_by()

        def the_strip(tag):
            return spec_strip(tracks.the_cutter(tag))
        def spec_strip(tag):
            return tracks.lstrip_special(tag)

        if attr == 'album' or attr == 'title':
            s = [(spec_strip(getattr(track, attr).lower()), 
            the_strip(getattr(track, 'artist').lower()), 
            spec_strip(getattr(track,'album').lower()), 
            getattr(track, 'track'), 
            track) for track in self.songs]
        elif attr == 'artist':
            s = [(the_strip(getattr(track, 'artist').lower()),
            the_strip(getattr(track, 'artist').lower()),
            spec_strip(getattr(track,'album').lower()), 
            getattr(track, 'track'), 
            track) for track in self.songs]
        else:
            s = [(getattr(track, attr), 
            the_strip(getattr(track, 'artist').lower()), 
            spec_strip(getattr(track,'album').lower()), 
            getattr(track, 'track'), 
            track) for track in self.songs]
        s.sort(reverse=reverse)
        self.songs = [track[4] for track in s]
        self.set_songs(self.songs)

    def get_sort_by(self):
        """
            Gets the sort order
        """
        for col in self.list.get_columns():
            if col.get_sort_indicator():
                return (self.col_map[col.get_title()], 
                    col.get_sort_order() == gtk.SORT_DESCENDING)
        return 'album', False

    def stop_icon_data_func(self, col, cellr, model, iter):
        """
            sets stop icon
        """

        item = model.get_value(iter, 0)
        image = None
        
        if item == self.exaile.player.stop_track:
            image = self.exaile.window.render_icon('gtk-stop', 
                gtk.ICON_SIZE_MENU) 
            image = image.scale_simple(12, 12, gtk.gdk.INTERP_BILINEAR)
        
        cellr.set_property('pixbuf', image)  
            
    def icon_data_func(self, col, cellr, model, iter):
        """
            sets track icon
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

        cellr.set_property('pixbuf', image)

    def rating_data_func(self, col, cellr, model, iter):
        item = model.get_value(iter, 0)
        if not item.rating: return
        idx = len(item.rating) / 2 - 1
        cellr.set_property('pixbuf', self.rating_images[idx])

    def length_data_func(self, col, cellr, model, iter):
        """ 
            Formats the track length
        """
        item = model.get_value(iter, 0)

        if item == 'podcast':
            cellr.set_property('text', item.length)
            return

        seconds = item.duration
        text = "%s:%02d" % (seconds / 60, seconds % 60)

        if item.type == 'stream':
            text = ''

        cellr.set_property('text', text)

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
        self.songs = tracks.TrackData()

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
            if check == song:
                self.update_iter(iter, song)
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

        pixbuf = xlmisc.get_text_icon(self.exaile.window, u'\u2610', 16, 16)
        icon_set = gtk.IconSet(pixbuf)
        
        factory = gtk.IconFactory()
        factory.add_default()        
        factory.add('exaile-queue-icon', icon_set)
        
        self.queue = tpm.append(_("Toggle Queue"), self.exaile.on_queue,
            'exaile-queue-icon')
        self.stop_track = tpm.append(_("Toggle: Stop after this Track"), 
            self.exaile.on_stop_track, 'gtk-stop')
        tpm.append_separator()
        n_selected = len(songs)

        if not songs or not songs[0].type == 'stream':
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

        em = xlmisc.Menu()

        em.append(_("Edit Information"), lambda e, f:
            track.TrackEditor(self.exaile, self), 'gtk-edit')
        em.append_separator()

        # edit specific common fields
        for menu_item in ('title', 'artist', 'album', 'genre', 'year'):
            # Obs.: The menu_item.capitalize() will be substituted by 
            # Title, Artist, Album and Year. Since these   
            # strings were already extracted in another part of exaile 
            # code, then _(menu_item.capitalize() will be substituted by 
            # the translated string in exaile.
            item = em.append(_("Edit %s") % _(menu_item.capitalize()),
                lambda w, e, m=menu_item: track.edit_field(self, m))

        em.append_separator()
        rm = xlmisc.Menu()
        self.rating_ids = []

        for i in range(0, 8):
            item = rm.append_image(self.rating_images[i],
                lambda w, e, i=i: track.update_rating(self, i))

        em.append_menu(_("Rating"), rm)
        tpm.append_menu(ngettext("Edit Track", "Edit Tracks", n_selected), em,
            'gtk-edit')
        bm = tpm.append(ngettext("Burn Track", "Burn Tracks", n_selected),
            self.burn_selected, 'gtk-cdrom')
        info = tpm.append(_("Information"), self.get_track_information,
            'gtk-info')
        tpm.append_separator()

        if not burn.check_burn_progs():
            bm.set_sensitive(False)

        if n_selected == 1 and self.get_selected_track() \
            and self.get_selected_track().type == 'lastfm':
            lfm = xlmisc.Menu()
            lfm.append('Ban', lambda *e: self.send_lastfm_command('ban'))
            lfm.append('Love', lambda *e: self.send_lastfm_command('love'))
            lfm.append('Skip', lambda *e: self.send_lastfm_command('skip'))
            tpm.append_menu(_("Last.FM Options"), lfm)
            tpm.append_separator()

        factory.add('exaile-track-icon', gtk.IconSet(
            gtk.gdk.pixbuf_new_from_file(os.path.join('images',
            'track.png'))))
        tpm.append(_("Show in Collection"), self.show_in_collection,
            'exaile-track-icon')
        tpm.append_separator()

        rm = xlmisc.Menu()
        self.remove_tracks = rm.append(_("Remove from Playlist"),
            self.delete_tracks, None, 'remove')
        self.playlists_menu = None

        rm.append(ngettext("Blacklist Track", "Blacklist Tracks", n_selected),
            self.exaile.on_blacklist)

        rm.append(ngettext("Delete Track", "Delete Tracks", n_selected),
            self.delete_tracks, 'gtk-delete', 'delete')
        tpm.append_menu(_("Remove"), rm, 'gtk-delete')

        # plugins menu items
        if self.exaile.plugins_menu.get_children():
            tpm.append_separator()

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

    def send_lastfm_command(self, command):
        if self.exaile.player.lastfmsrc:
            self.exaile.player.lastfmsrc.control(command)


    def get_track_information(self, widget, event=None):
        """
            Shows the track information tab
        """
        t = self.get_selected_track()
        track.show_information(self.exaile, t)

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
        settings = self.exaile.get_settings_dir()
        cache = "%s%s%s" % (settings, os.sep, "cache")
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
        settings = self.exaile.get_settings_dir()
        cache = "%s%s%s" % (settings, os.sep, "cache")
        if not os.path.isdir(cache): os.mkdir(cache)

        try:
            f = open("%s%sradioplugin_%s_%s.tab" % (cache, os.sep, plugin, genre), "w")
            for track in self.songs:
                f.write("%s\t%s\t%s\t%s\t%s\n" % (track.album, track.artist, track.title,
                    track.loc, track.bitrate))
            f.close()
        except IOError:
            xlmisc.log('Could not save station list')

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
            for track in tracks:
                delete.append(track)

            while len(delete) > 0:
                track = delete.pop()
                path_id = xl.tracks.get_column_id(self.db, 'paths', 'name', track.loc)
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

                        playlist_id = xl.tracks.get_column_id(self.db, t, 'name',
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
            if blacklisting: self.exaile.show_blacklist_manager(False)
            self.exaile.on_search()
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
            path_id = tracks.get_column_id(self.db, 'paths', 'name', track.loc)
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
