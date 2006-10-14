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
import xlmisc, common, track, tracks
import copy, time, urllib
from gettext import gettext as _
from pysqlite2.dbapi2 import OperationalError
import pygtk
pygtk.require('2.0')
import gtk


class TracksListCtrl(gtk.VBox):
    """
        Represents the track/playlist table
    """
    col_items = ['', "#",
        _("Title"), _("Artist"), _("Album"), _("Length"),
        _("Rating"), _("Year"), _("Genre"), _("Bitrate")]
    col_map = {
        '#': 'track',
        _('Title'): 'title',
        _('Artist'): 'artist',
        _('Album'): 'album',
        _('Length'): 'length',
        _('Rating'): 'rating',
        _('Year'): 'year',
        _('Genre'): 'genre',
        _('Bitrate'): 'bitrate'
        }
    prep = "track"
    type = 'track'
    default_sizes = [30, 30, 200, 150, 150, 50, 80, 50, 100, 30]

    def __init__(self, exaile, queue=False):
        """
            Expects an exaile instance, the parent window, and whether or not
            this is a queue window.  If it's not a queue window, the track
            popup menu will be initialized.
        """
        gtk.VBox.__init__(self)
        self.exaile = exaile
        self.list = gtk.TreeView()
        self.list.set_rules_hint(True)
        self.songs = tracks.TrackData()
        self.model = gtk.ListStore(object, gtk.gdk.Pixbuf, int, str, str, str,
            str, str, str, str, str)
        self.list.set_model(self.model)
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.list)
        self.pack_start(self.scroll, True, True)
        self.scroll.show_all()
        selection = self.list.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.playimg = self.exaile.window.render_icon('gtk-media-play',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.pauseimg = self.exaile.window.render_icon('gtk-media-pause',
            gtk.ICON_SIZE_SMALL_TOOLBAR)

        self.db = exaile.db
        self.inited = False
        self.queue = queue
        self.ipod = False
        self.playlist = None
        self.dragging = False
        self.setup_columns()

        self.show()

        if not self.type == 'blacklist':
            self.setup_dragging()

        if self.type == 'track':
            self.setup_events()

    def setup_dragging(self):
        """
            Sets up drag and drop
        """
        self.targets = [("text/uri-list", 0, 0)]
        self.list.drag_source_set(
            gtk.gdk.BUTTON1_MASK, self.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        self.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT)
        self.list.connect('drag_data_received', self.drag_data_received)
        self.__dragging = False
        self.list.connect('drag_begin', self.__drag_begin)
        self.list.connect('drag_end', self.__drag_end)
        self.list.connect('drag_motion', self.__drag_motion)
        self.list.connect('button_release_event', self.__button_release)
        self.list.connect('drag_data_get', self.drag_get_data)
        self.list.drag_source_set_icon_stock('gtk-dnd')

    def __button_release(self, button, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.__dragging: return True
        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True
        selection = self.list.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.list.get_path_at_pos(x, y)
        if not path: return False
        selection.unselect_all()
        selection.select_path(path[0])

    def __drag_end(self, list, context):
        """
            Called when the dnd is ended
        """
        self.__dragging = False
        self.list.unset_rows_drag_dest()
        self.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

    def __drag_begin(self, list, context):
        """
            Called when dnd is started
        """
        self.__dragging = True

        context.drag_abort(gtk.get_current_event_time())
        selection = self.list.get_selection()
        if selection.count_selected_rows() > 1:
            self.list.drag_source_set_icon_stock('gtk-dnd-multiple')
        else: self.list.drag_source_set_icon_stock('gtk-dnd')
        return False

    def __drag_motion(self, treeview, context, x, y, timestamp):
        """
            Called when a row is dragged over this treeview
        """
        self.list.enable_model_drag_dest(self.targets,
            gtk.gdk.ACTION_DEFAULT)
        info = treeview.get_dest_row_at_pos(x, y)
        if not info: return
        treeview.set_drag_dest_row(info[0], info[1])

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when data is recieved
        """
        self.list.unset_rows_drag_dest()
        self.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
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
            if l.find("ipod://") > -1:
                song = self.exaile.ipod_panel.get_song(
                    l.replace("ipod://", ""))
            else:
                song = self.exaile.all_songs.for_path(l)
                if not song:
                    song = tracks.read_track(self.exaile.db, self.exaile.all_songs,
                        l, adddb=False)

            if not song or song in self.songs: continue

            if not drop_info:
                # if there's no drop info, just add it to the end
                if song: self.append_song(song)
            else:
                if not first:
                    first = True
                    iter = self.model.insert_before(iter, [song, None, 
                        song.track, song.title, song.artist, song.album, 
                        song.length, song.rating, song.year, song.genre, 
                        song.bitrate])
                else:
                    iter = self.model.insert_after(iter, [song, None, 
                        song.track, song.title, song.artist,
                        song.album, song.length, song.rating, song.year, 
                        song.genre, song.bitrate])
                if counter >= 20:
                    xlmisc.finish()
                    counter = 0
                else:
                    counter += 1
            if not song in self.playlist_songs:
                self.playlist_songs.append(song)


        if context.action == gtk.gdk.ACTION_MOVE:
            context.finish(True, True, etime)
        self.update_songs()
        if self.type != 'queue':
            self.exaile.update_songs(None, False)
        self.exaile.status.set_first(None)

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
        if not song in self.songs: return None
        index = self.songs.index(song)
        path = (index + 1,)
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
        self.list.connect('row-activated', self.exaile.play)
        self.list.connect('button_press_event', self.show_tracks_popup)
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

            if isinstance(song, media.iPodTrack):
                loc.append("ipod://%s" % urllib.quote(str(song.loc)))
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

        # delete key
        if event.keyval == 65535:
            selection = self.list.get_selection()
            (model, pathlist) = selection.get_selected_rows()

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

    def setup_columns(self):
        """
            Sets up the columns for this table
        """

        self._col_count = 0
        self._length_id = -1
        count = 1
        for name in self.col_items:

            # get cell renderer
            if count == 1:
                cellr = gtk.CellRendererPixbuf()
            else:
                cellr = gtk.CellRendererText()

            show = self.exaile.settings.get_boolean("show_%s_col_%s" %
                (self.prep, name), True)
            if count == 1 or show:
                if count == 1:
                    col = gtk.TreeViewColumn(name, cellr, pixbuf=count)
                else:
                    col = gtk.TreeViewColumn(name, cellr, text=count)

                if count == 1:
                    col.set_cell_data_func(cellr, self.icon_data_func)
                if name == _("Length"):
                    col.set_cell_data_func(cellr, self.length_data_func)
                if name == "#":
                    col.set_cell_data_func(cellr, self.track_data_func)

                name = name + "_%scol_width" % self.prep
                width = self.exaile.settings.get_int(name, 
                    self.default_sizes[count - 1])
                col.set_fixed_width(width)

                if self.type != 'queue':
                    if count > 1:
                        col.connect('clicked', self.set_sort_by)
                    col.set_sort_column_id(count)
                    col.set_reorderable(True)
                    col.set_resizable(True)
                col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                self.list.append_column(col)
            count = count + 1
        self.list.connect('focus_out_event', self.tree_lost_focus)

    def track_data_func(self, col, cell, model, iter):
        """
            Track number
        """
        item = model.get_value(iter, 0)
        if item.track is None or item.track == -1:
            cell.set_property('text', '')
        else:
            cell.set_property('text', item.track)

    # sort functions courtesy of listen (http://listengnome.free.fr), which
    # are in turn, courtesy of quodlibet.  Obviously the Quodlibet authors are
    # a lot smarter than I am :)
    def set_sort_by(self, column):
        """
            Sets the sort column
        """
        title = column.get_title()
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
        s = [(getattr(track, attr), track) for track in self.songs]
        s.sort()
        if reverse: s.reverse()
        self.songs = [track[1] for track in s]
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
            
    def tree_lost_focus(self, widget, event):
        """
            Called when the tree loses focus... to save column widths
        """
        for col in self.list.get_columns():
            name = col.get_title() + "_%scol_width" % self.prep
            self.exaile.settings[name] = col.get_width()

    def icon_data_func(self, col, cellr, model, iter):
        """
            sets track icon
        """

        item = model.get_value(iter, 0)
        image = None
        if item.is_playing(): image = self.playimg 
        elif item.is_paused(): image = self.pauseimg
        elif item in self.exaile.queued:
            index = self.exaile.queued.index(item)
            image = xlmisc.get_text_icon(self.exaile.window,
                str(index + 1), 20, 20)
        cellr.set_property('pixbuf', image)

    def length_data_func(self, col, cellr, model, iter):
        """ 
            Formats the track length
        """
        item = model.get_value(iter, 0)

        if isinstance(item, media.PodcastTrack):
            cellr.set_property('text', item.length)
            return

        seconds = item.duration
        text = "%s:%02d" % (seconds / 60, seconds % 60)

        if isinstance(item, media.StreamTrack):
            text = ''

        cellr.set_property('text', text)

    def update_col_settings(self):
        """
            Updates the settings for a specific column
        """
        columns = self.list.get_columns()
        for col in columns:
            self.list.remove_column(col)

        self.setup_columns()
        self.list.queue_draw()

    def set_songs(self, songs, update_playlist=True):
        """
            Sets the songs in this table (expects a list of tracks)
        """
        self.songs = tracks.TrackData()
        self.model.clear()
        if update_playlist: self.playlist_songs = songs
        for song in songs:
            self.append_song(song)

    def append_song(self, song):
        """
            Adds a song to this view
        """
        self.model.append([song, None, song.track, song.title, song.artist,
            song.album, song.length, song.rating, song.year, song.genre,
            song.bitrate])
        if not song in self.songs: self.songs.append(song)

    def update_iter(self, iter, song):
        """
            Updates the track at "iter"
        """
        self.model.insert_after(iter, [song, None, song.track, song.title,  
            song.artist, song.album, song.length, song.rating, song.year, 
            song.genre, song.bitrate])
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

    def setup_tracks_menu(self, ipod=False):
        """
            Sets up the popup menu for the tracks list
        """
        self.ipod = ipod

        tpm = xlmisc.Menu()
        self.tpm = tpm

        self.queue = tpm.append(_("Toggle Queue"), self.exaile.on_queue)
        tpm.append_separator()
        songs = self.get_selected_tracks()

        if not songs or not isinstance(songs[0], media.StreamTrack):
            pm = xlmisc.Menu()
            self.new_playlist = pm.append(_("New Playlist"),
                self.exaile.playlists_panel.on_add_playlist)
            pm.append_separator()
            rows = self.db.select("SELECT playlist_name FROM playlists ORDER BY"
                " playlist_name")
            for row in rows:
                pm.append(row[0], self.exaile.playlists_panel.add_items_to_playlist)

            tpm.append_menu(_("Add to Playlist"), pm)

        else:
            self.playlists_menu = xlmisc.Menu()
            all = self.db.select("SELECT radio_name FROM radio "
                "ORDER BY radio_name")
            for row in all:
                i = self.playlists_menu.append(row[0],
                    self.exaile.radio_panel.add_items_to_station)

            self.playlists_menu.append_separator()
            self.new_playlist = self.playlists_menu.append(_("New Station"),
                self.exaile.radio_panel.on_add_to_station)

            tpm.append_menu(_("Add to Saved Stations"),
                self.playlists_menu)

        em = xlmisc.Menu()

        em.append(_("Edit Information"), lambda e, f:
            track.TrackEditor(self.exaile, self))
        em.append_separator()

        # edit specific common fields
        for menu_item in ('title', 'artist', 'album', 'genre', 'year'):
            item = em.append("Edit %s" % menu_item.capitalize(),
                self.__edit_field, data=menu_item)

        em.append_separator()
        if not ipod:
            rm = xlmisc.Menu()
            self.rating_ids = []

            for i in range(0, 8):
                string = "* " * (i + 1)
                item = rm.append(string, self.__update_rating,
                    None, i)

            em.append_menu(_("Rating"), rm
)
        tpm.append_menu(_("Edit Track(s)"), em)
        info = tpm.append(_("Information"), self.get_track_information)
        tpm.append_separator()

        rm = xlmisc.Menu()
        self.remove_tracks = rm.append(_("Remove from Playlist"),
            self.exaile.delete_tracks, None, 'remove')
        self.playlists_menu = None

        if not ipod:
            rm.append(_("Blacklist Track(s)"), self.exaile.on_blacklist)

        rm.append(_("Delete Track(s)"), self.exaile.delete_tracks,
            'gtk-delete', 'delete')
        tpm.append_menu(_("Remove"), rm)

    def __edit_field(self, widget, data):
        """
            Edits one field in a list of tracks
        """
        songs = self.get_selected_tracks()
        if not songs: return
        text = getattr(songs[0], data)

        dialog = xlmisc.TextEntryDialog(self.exaile.window, 
            "Enter the %s for the selected track(s)" % data.capitalize(),
            "Edit %s" % data.capitalize())
        dialog.set_value(text)

        if dialog.run() == gtk.RESPONSE_OK:
            value = dialog.get_value()
            errors = ''
            for song in songs:
                setattr(song, data, value)
                try:
                    song.write_tag(self.db)
                except xlmisc.MetaIOException, e: 
                    errors += e.reason + "\n"
                except:
                    errors += "Could not write tag for %s\n" % song.loc
                    xlmisc.log_exception()

                xlmisc.finish()
                self.refresh_row(song)

            if errors:
                common.scrolledMessageDialog(self.exaile.window,
                   errors, "Error writing tags")                    
            
        dialog.destroy()

    def get_track_information(self, widget, event=None):
        """
            Shows the track information tab
        """
        t = self.get_selected_track()
        track.show_information(self.exaile, t)

    def __update_rating(self, widget, event):
        """
            Updates the rating based on which menu id was clicked
        """
        text = widget.child.get_label()
        rating = 1
        if text.find('*') > -1:
            rating = len(text) / 2

        cur = self.db.cursor()
        for track in self.get_selected_tracks():
            self.db.execute("UPDATE tracks SET user_rating=? WHERE path=?",
                (rating, track.loc))
            track.rating = rating
            self.refresh_row(track)

    def show_tracks_popup(self, button, event):
        """
            The popup menu that is displayed when you right click in the
            playlist
        """
        selection = self.list.get_selection()
        (x, y) = event.get_coords()
        x = int(x)
        y = int(y)
        path = self.list.get_path_at_pos(x, y)
        if not path: return True

        if event.button != 3: 
            if selection.count_selected_rows() <= 1: return False
            else: 
                if selection.path_is_selected(path[0]): 
                    if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        selection.unselect_path(path[0])
                    return True
                elif not event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    return True
                return False
        self.setup_tracks_menu()

        ipod = self.ipod

        self.tpm.popup(None, None, None, 0, gtk.get_current_event_time())
        if selection.count_selected_rows() <= 1: return False
        else: return True

    def load(self, genre):
        """
            Loads the track information from a cache file if it exists.
            If loading it fails, False is returned, else True is returned
        """
        settings = self.exaile.get_settings_dir()
        cache = "%s%s%s" % (settings, os.sep, "cache")
        if not os.path.isdir(cache): os.mkdir(cache)
        f = "%s%sradio_%s.tab" % (cache, os.sep, genre)
        if not os.path.isfile(f): return False
        songs = []
        try:
            f = open(f, "r")
            for line in f.readlines():
                line = line.strip()
                fields = line.split("\t")
                info = ({
                    "artist": fields[0],
                    "title": fields[1],
                    "url": fields[2],
                    "bitrate": fields[3].replace("k", "")
                })

                track = tracks.RadioTrack(info)
                songs.append(track)
        except:
            xlmisc.log_exception()
            return False
        self.set_songs(songs)
        self.playlist_songs = songs
        return True

    def save(self, genre):
        """
            Saves the track information to a track file.
        """
        settings = self.exaile.get_settings_dir()
        cache = "%s%s%s" % (settings, os.sep, "cache")
        if not os.path.isdir(cache): os.mkdir(cache)
        f = open("%s%sradio_%s.tab" % (cache, os.sep, genre), "w")
        for track in self.songs:
            f.write("%s\t%s\t%s\t%s\n" % (track.artist, track.title,
                track.loc, track.bitrate))
        f.close()

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
        TracksListCtrl.setup_tracks_menu(self, True)
        self.deblacklist = self.tpm.append(_("Remove from Blacklist"), 
            self.__de_blacklist)

    def __de_blacklist(self, item, event):
        """
            Removes items from the blacklist
        """
        tracks = self.get_selected_tracks()
        cur = self.db.cursor()
        remove = []
        for track in tracks:
            remove.append(track)

        for track in remove:
            self.playlist_songs.remove(track)
            try: self.exaile.songs.remove(track)
            except: pass
            self.db.execute("UPDATE tracks SET blacklisted=0 WHERE path=?", (track.loc,))
            if not track in self.exaile.all_songs:
                self.exaile.all_songs.append(track)

        self.set_songs(self.exaile.songs)

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

        self.set_songs(self.exaile.queued)

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

        queue = self.exaile.queued
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

        queue = self.exaile.queued
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
            self.exaile.queued.remove(track)

        self.set_songs(self.exaile.queued)
        update_queued(self.exaile)

    def clear_queue(self, item):
        """
            Clears the queue
        """
        while self.exaile.queued:
            self.exaile.queued.pop()

        self.set_songs(self.exaile.queued)
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
        self.exaile.queued = []
        for song in self.songs:
            self.exaile.queued.append(song)

        update_queued(self.exaile)

def update_queued(exaile):
    """ 
        If the queue manager is showing, this updates it
    """
    nb = exaile.playlists_nb
    for i in range(0, nb.get_n_pages()):
        page = nb.get_nth_page(i)
        if isinstance(page, QueueManager):
            page.set_songs(exaile.queued)

    if exaile.queued:
        exaile.queue_count_label.set_label("%d track(s) queued" % 
            len(exaile.queued))
    else:
        exaile.queue_count_label.set_label("")
