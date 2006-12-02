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

import xl.tracks, os, sys, md5, random, db, tracks, xlmisc
import common, trackslist, shoutcast, filtergui
import media, time, thread, re, copy, threading
import urllib
from xml.dom import minidom
from filtergui import MultiEntryField, EntryField

try:
    from pysqlite2 import dbapi2 as sqlite
except ImportError:
    from sqlite3 import dbapi2 as sqlite

from gettext import gettext as _
from popen2 import popen3 as popen
import pygtk, audioscrobbler
pygtk.require('2.0')
import gtk, gobject
random.seed()

try:
    import gpod
    IPOD_AVAILABLE = True
except:
    IPOD_AVAILABLE = False

N_ = lambda x: x

class EntrySecondsField(MultiEntryField):
	def __init__(self, result_generator):
		MultiEntryField.__init__(self, result_generator, n=1,
				labels=(None, _('seconds')),
				widths=(50,))

class EntryAndEntryField(MultiEntryField):
	def __init__(self, result_generator):
		MultiEntryField.__init__(self, result_generator, n=2,
				labels=(None, _('and'), None),
				widths=(50, 50))

CRITERIA = [
		(N_('Artist'), [
			(N_('is'), (EntryField, lambda x:
				'artist = "%s"' % x)),
			(N_('contains'), (EntryField, lambda x:
				'artist LIKE "%%%s%%"' % x)),
			]),
		(N_('Genre'), [
			(N_('is'), (EntryField, lambda x:
				'genre = "%s"' % x)),
			(N_('contains'), (EntryField, lambda x:
				'genre LIKE "%%%s%%"' % x)),
			]),
		(N_('Rating'), [
			(N_('at least'), (EntryField, lambda x:
				'user_rating >= %s' % x)),
			(N_('at most'), (EntryField, lambda x:
				'user_rating <= %s' % x)),
			(N_('between'), (EntryAndEntryField, lambda x, y:
				'user_rating BETWEEN %s AND %s' % (x, y))),
			]),
		(N_('Year'), [
			(N_('before'), (EntryField, lambda x:
				'year < %s' % x)),
			(N_('after'), (EntryField, lambda x:
				'year > %s' % x)),
			(N_('between'), (EntryAndEntryField, lambda x, y:
				'year BETWEEN %s AND %s' % (x, y))),
			]),
		(N_('Length'), [
			(N_('at least'), (EntrySecondsField, lambda x:
				'length >= %s' % x)),
			(N_('at most'), (EntrySecondsField, lambda x:
				'length <= %s' % x)),
			]),
		]

def get_sql(crit1, crit2, filter):
    filter = eval(filter)

    sql = None
    for item1 in CRITERIA:
        if item1[0] == crit1:
            for item2 in item1[1]:
                if item2[0] == crit2:
                    sql = item2[1][1](*filter)

    return sql

class AlbumWrapper(object):
    """
        Wraps an album
    """
    def __init__(self, name):
        """
            Initializes the class
        """
        self.name = name

    def __str__(self):
        """
            Returns the name
        """
        return self.name

class CollectionPanel(object):
    """
        Represents the entire collection in a tree
    """
    name = 'col'
    def __init__(self, exaile):
        """
            Initializes the collection panel. Expects a parent and exaile
            object
        """
        self.xml = exaile.xml
        self.exaile = exaile
        self.db = exaile.db

        self.scan_label = None
        self.scan_progress = None
        self.showing = False
        self.tree = None
        self.keyword = None
        self.track_cache = dict()
        self.start_count = 0
        self.ipod = False
        self.artist_image = gtk.gdk.pixbuf_new_from_file('images%sartist.png' %
            os.sep)
        self.album_image = self.exaile.window.render_icon('gtk-cdrom', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.track_image = gtk.gdk.pixbuf_new_from_file('images%strack.png' % 
            os.sep)
        self.ipod_image = xlmisc.get_icon('gnome-dev-ipod')
        self.genre_image = gtk.gdk.pixbuf_new_from_file('images%sgenre.png' %
            os.sep)
        self.iplaylist_image = gtk.gdk.pixbuf_new_from_file('images%splaylist.png' % os.sep)
        self.connect_id = None
        self.setup_widgets()

    def setup_widgets(self):
        """
            Sets up the widgets for this panel
        """
        self.box = self.xml.get_widget('%s_box' % self.name)
        self.choice = self.xml.get_widget('%s_combo_box' % self.name)

        active = self.exaile.settings.get_int('active_view', 0)
        self.choice.set_active(active)
        self.xml.get_widget('%s_refresh_button' % self.name).connect('clicked',
            self.load_tree)
        self.xml.get_widget('%s_combo_box' % self.name).connect('changed',
            self.load_tree)
        self.filter = xlmisc.ClearEntry(self.key_release)
        self.xml.get_widget('%s_filter_box' % 
            self.name).pack_start(self.filter.entry,
            True, True)
        self.filter.connect('activate', self.on_search)
        self.key_id = None
        self.filter.set_sensitive(False)
        self.create_popup()

    def key_release(self, *e):
        """
            Called when someone releases a key.
            Sets up a timer to simulate live-search
        """
        if self.key_id:
            gobject.source_remove(self.key_id)
            self.key_id = None

        self.key_id = gobject.timeout_add(700, self.on_search)

    def update_progress(self, percent):
        """
            Updates scanning progress meter
        """
        if percent <= -1:
            self.scan_label.hide()
            self.progress_box.hide()
            self.progress.hide()
            self.stop_button.hide()
            self.showing = False
            self.exaile.status.set_first(_("Finished scanning collection."),
                2000)
            self.scan_label.destroy()
            self.progress_box.destroy()
            self.stop_button.destroy()
            self.progress.destroy()
            self.scan_label = None

        else:
            if not self.scan_label:
                self.progress = gtk.ProgressBar()
                self.progress_box = gtk.HBox(spacing=2)
                self.stop_button = gtk.Button()
                image = gtk.Image()
                image.set_from_stock('gtk-stop', gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.stop_button.set_image(image)
                self.stop_button.connect('clicked', self.stop_scan)
                self.progress_box.pack_start(self.progress, True, True)
                self.progress_box.pack_start(self.stop_button, False, False)

                self.box.pack_end(self.progress_box, False, False)
                self.scan_label = gtk.Label(_("Scanning..."))
                self.scan_label.set_alignment(0, 0)
                self.box.pack_end(self.scan_label, False, False)
           
            if not self.showing:
                self.showing = True
                self.progress.show()
                self.stop_button.show()
                self.progress_box.show_all()
                self.scan_label.show()
            self.progress.set_fraction(percent)

    def stop_scan(self, widget):
        """
            Stops the library scan
        """
        if tracks.PopulateThread.running:
            tracks.PopulateThread.stopped = True

    def on_search(self, widget=None, event=None):
        """
            Searches tracks and reloads the tree.  A timer is started
            in LoadTree if keyword is not None which will expand the items
            of the tree until the matched node is found
        """
        self.keyword = self.filter.get_text()
        self.start_count += 1
        if isinstance(self, iPodPanel):
            self.load_tree(None, False)
        else:
            self.load_tree()

    def create_popup(self):
        """
            Creates the popup menu for this tree
        """
        menu = xlmisc.Menu()
        self.append = menu.append(_("Append to Current"),
            self.append_items)

        pm = xlmisc.Menu()
        self.new_playlist = pm.append(_("Add to Playlist"),
            self.append_items)
        pm.append_separator()

        rows = self.db.select("SELECT name FROM playlists ORDER BY"
            " name")

        for row in rows:
            pm.append(row[0], self.add_to_playlist)

        menu.append_menu(_("Add to Playlist"), pm)
        self.queue_item = menu.append(_("Queue Items"), self.append_items)
        menu.append_separator()
        self.blacklist = menu.append(_("Blacklist Selected"),
            self.append_items)
        self.remove = menu.append(_("Delete Selected"), 
            self.append_items)
        self.menu = menu

    def add_to_playlist(self, widget, event):
        """
            Adds items to the playlist
        """
        playlist = widget.get_child().get_label()
        items = self.append_items(None, None, True)
        self.exaile.playlists_panel.add_items_to_playlist(playlist, items)

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        loc = self.append_items(None, None, True)

        if isinstance(self, iPodPanel):
            loc = ["ipod://%s" % urllib.quote(l.loc) for l in loc]
        else:
            loc = [urllib.quote(str(l.loc)) for l in loc]

        selection.set_uris(loc)

    def append_recursive(self, iter, add, queue=False):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)        
        while True:
            if self.model.iter_has_child(iter):
                self.append_recursive(iter, add, queue)
            else:
                track = self.model.get_value(iter, 1)
                add.append(track.loc)
            
            iter = self.model.iter_next(iter)
            if not iter: break

    def append_items(self, item=None, event=None, return_only=False):
        """
            Adds items to the songs list based on what is selected in the tree
            The songs are then added to a playlist, queued, removed, or 
            blacklisted, depending on which menu item was clicked
        """
        queue = False
        if item == self.queue_item: queue = True
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        found = [] 
        for path in paths:
            iter = self.model.get_iter(path)
            if self.model.iter_has_child(iter):
                self.append_recursive(iter, found, queue)
            else:
                track = self.model.get_value(iter, 1)
                found.append(track.loc)

        # create an sql query based on all of the paths that were found.
        # this way we can order them by track number to make sure they
        # are added to the playlist as they are sorted in the album
#        add = ["path=%s" % self.db.p for x in found]
#        where = " OR ".join(add)
#        cur = self.db.cursor()
#        add = tracks.TrackData()
#        table = "tracks"
#        if self.ipod: table = "ipod_tracks"
#        rows = self.db.select("SELECT path FROM %s WHERE %s ORDER BY artist, " \
#            "album, track, title" % (table, where), found)

#        for row in rows:
#            add.append(self.all.for_path(row[0]))

        add = tracks.TrackData()

        for row in found:
            add.append(self.all.for_path(row))

        if return_only: return add

        ipod_delete = []
        if item == self.remove:
            result = common.yes_no_dialog(self.exaile.window,
                _("Are you sure you want to permanently remove the " \
                "selected tracks from disk?"))

            if result != gtk.RESPONSE_YES: return
            for track in add:
                if track.type == 'ipod':
                    ipod_delete.append(track)
                else:
                    os.remove(track.loc)

            for track in add:
                path_id = tracks.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                self.db.execute("DELETE FROM tracks WHERE path=?", (path_id,))
                self.db.execute("DELETE FROM playlist_items WHERE path=?",(path_id,))

        if item == self.blacklist:
            result = common.yes_no_dialog(self.exaile.window,
                _("Are you sure you want to blacklist the selected tracks?"))
            if result != gtk.RESPONSE_YES: 
                return
            for track in add:
                path_id = tracks.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                self.db.execute("UPDATE tracks SET blacklisted=1 WHERE ?", (path_id,))
            
        if item == self.blacklist or item == self.remove:
            for track in add:
                try: self.exaile.all_songs.remove(track)
                except: pass
                try: self.exaile.songs.remove(track)
                except: pass
                try: self.exaile.playlist_songs.remove(track)
                except: pass

            if self.exaile.tracks: 
                self.exaile.tracks.set_songs(self.exaile.songs)
            self.track_cache = dict()
            if ipod_delete:
                self.exaile.ipod_panel.delete_tracks(ipod_delete)
                self.save_database()
            else:
                self.load_tree()
            return

        if item == self.new_playlist:
            self.exaile.playlists_panel.on_add_playlist(item, None, add)
            return


        self.exaile.append_songs(add, queue, True)

    def button_release(self, widget, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.__dragging: return True
        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True
        selection = self.tree.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.tree.get_path_at_pos(x, y)
        if not path: return False
        selection.unselect_all()
        selection.select_path(path[0])

    def button_press(self, widget, event):
        """
            Called when someone clicks on the tree
        """
        selection = self.tree.get_selection()

        (x, y) = event.get_coords()
        x = int(x); y = int(y)
        path = self.tree.get_path_at_pos(x, y)
        if event.type == gtk.gdk._2BUTTON_PRESS:
            (model, paths) = selection.get_selected_rows()

            # check to see if it's a double click on an album
            if len(paths) == 1:
                iter = self.model.get_iter(path[0])
                object = self.model.get_value(iter, 1)
                if isinstance(object, AlbumWrapper):
                    self.append_items()
                    return

            for path in paths:
                iter = self.model.get_iter(path)
                object = self.model.get_value(iter, 1)
                if self.model.iter_has_child(iter):
                    self.tree.expand_row(path, False)
                elif isinstance(object, iPodPlaylist):
                    self.open_playlist()
                else:
                    self.append_items() 
            return False

        iter = self.model.get_iter(path[0])
        object = self.model.get_value(iter, 1)
        if isinstance(object, iPodPlaylist):
            self.create_ipod_menu(object.root)
            selection.unselect_all()
            selection.select_path(path[0])
            self.ipod_menu.popup(None, None, None,
                event.button, event.time)
            return True
        self.create_popup()
        self.menu.popup(None, None, None, event.button, event.time)
        if selection.count_selected_rows() <= 1: return False
        return True

    def track_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, iPodPlaylist):
            cell.set_property('text', str(object))
        elif isinstance(object, media.Track):
            cell.set_property('text', str(object.title))
        else:
            cell.set_property('text', str(object))

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        pass

    def load_tree(self, event=None):
        """
            Builds the tree.  If self.keyword is not None, it will start a timer
            that will expand each node until a node that matches the keyword
            is found
        """
        self.current_start_count = self.start_count
        if not self.tree:
            self.tree = xlmisc.DragTreeView(self, self.ipod)
            self.tree.set_headers_visible(False)
            container = self.xml.get_widget('%s_box' % self.name)
            scroll = gtk.ScrolledWindow()
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            scroll.add(self.tree)
            scroll.set_shadow_type(gtk.SHADOW_IN)
            container.pack_start(scroll, True, True)
            container.show_all()

            selection = self.tree.get_selection()
            selection.set_mode(gtk.SELECTION_MULTIPLE)
            pb = gtk.CellRendererPixbuf()
            cell = gtk.CellRendererText()
            col = gtk.TreeViewColumn('Text')
            col.pack_start(pb, False)
            col.pack_start(cell, True)
            col.set_attributes(pb, pixbuf=0)
            self.tree.append_column(col)
            col.set_cell_data_func(cell, self.track_data_func)

        # clear out the tracks if this is a first time load or the refresh
        # button is pressed
        if event: 
            print "Clearing tracks cache"
            self.tracks_cache = dict()

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.model_blank = gtk.TreeStore(gtk.gdk.Pixbuf, object)

        self.tree.set_model(self.model_blank)
        self.root = None
    
        if isinstance(self, iPodPanel) and self.lists:
            root_playlist = self.lists[0]
            other = self.lists[1:]

            self.iroot = self.model.append(self.root, [self.ipod_image, root_playlist])

            for playlist in other:
                item = self.model.append(self.iroot, [self.iplaylist_image, playlist])

            self.root = self.model.append(self.root, [self.ipod_image, _("iPod Collection")])

        self.order = tuple()
        self.image_map = ({
            "artist": self.artist_image,
            "album": self.album_image,
            "genre": self.genre_image,
            "title": self.track_image
        })

        if self.keyword == "": self.keyword = None

        if self.choice.get_active() == 2:
            self.order = ('genre', 'artist', 'album', 'track', 'title')
            where = """
                SELECT 
                    paths.name, 
                    artists.name, 
                    track, 
                    title 
                FROM tracks, paths, artists 
                WHERE 
                    blacklisted=0 AND 
                    (
                        paths.id=tracks.path AND 
                        artists.id=tracks.artist
                    ) 
                ORDER BY 
                    LOWER(genre), 
                    track, 
                    title
            """

        if self.choice.get_active() == 0:
            self.order = ('artist', 'album', 'track', 'title')
            where = """
                SELECT 
                    paths.name, 
                    artists.name, 
                    albums.name, 
                    track,
                    title 
                FROM tracks, paths, albums, artists 
                WHERE
                    blacklisted=0 AND 
                    (
                        paths.id=tracks.path AND 
                        albums.id=tracks.album AND 
                        artists.id=tracks.artist
                    ) 
                ORDER BY 
                    THE_CUTTER(artists.name), 
                    LOWER(albums.name), 
                    track, 
                    title
            """

        if self.choice.get_active() == 1:
            self.order = ('album', 'track', 'title')
            where = """
                SELECT 
                    paths.name, 
                    albums.name, 
                    track, 
                    title
                FROM tracks, albums, paths, artists
                WHERE 
                    blacklisted=0 AND
                    (
                        paths.id=tracks.path AND
                        albums.id=tracks.album AND
                        artists.id=tracks.artist 
                    )
                ORDER BY 
                    LOWER(albums.name), 
                    track, 
                    THE_CUTTER(artists.name), 
                    title
            """

        # save the active view setting
        self.exaile.settings['active_view'] = self.choice.get_active()

        all = self.exaile.all_songs

        if self.ipod: 
            all = self.all
        else: self.all = all

        if not self.keyword and not self.ipod and \
            self.choice.get_active() == 0:
            songs = all
        else:
            if self.track_cache.has_key("%s %s" % (where, self.keyword)) \
                and self.track_cache["%s %s" % (where, self.keyword)] and \
                not self.ipod:
                songs = self.track_cache["%s %s" % (where, self.keyword)]
            else:
                songs = xl.tracks.search_tracks(self.exaile.window, self.db,
                    all, self.keyword, None, where, ipod=self.ipod)
        self.track_cache["%s %s" % (where, self.keyword)] = songs

        if self.current_start_count != self.start_count: return

        self.append_info(self.root, songs)

        if self.connect_id: gobject.source_remove(self.connect_id)
        self.connect_id = None
        self.filter.set_sensitive(True)

    @common.threaded
    def append_info(self, node, songs=None, unknown=False):
        """
            Appends all related info and organizes the tree based on self.order
            Only the very last item of self.order will be a child node
        """

        order_nodes = xl.common.idict()
        order = []
        last_songs = []
        for field in self.order:
            if field == "track": continue
            order.append(field)

        for field in order:
            order_nodes[field] = xl.common.idict()

        expanded_paths = []
        for track in songs:
            if self.current_start_count != self.start_count: return

            parent = node
            last_parent = None
            string = ""
            first = True
            for field in order:
                node_for = order_nodes[field]
                if field == "track": continue
                info = getattr(track, field)
                if info == "": 
                    if not unknown and first:
                        last_songs.append(track)
                        break
                    info = "Unknown"
                first = False

                if field == "title":
                    n = self.model.append(parent, [self.track_image,
                        track])
                else:
                    string = "%s - %s" % (string, info)
                    if not string in node_for:
                        if field == 'album':
                            info = AlbumWrapper(info)

                        parent = self.model.append(parent, 
                            [self.image_map[field], info])

                        data = "_%s" % field
                        if info == "track": info = track
                        node_for[string] = parent
                    else: parent = node_for[string]

                if self.keyword and last_parent:
                    if str(info).lower().find(self.keyword.lower()) > -1:
                        expanded_paths.append(self.model.get_path(
                            last_parent))
                last_parent = parent

        # make sure "Unknown" items end up at the end of the list
        if not unknown and last_songs:
            self.append_info(self.root, last_songs, True)

        gobject.idle_add(self.tree.set_model, self.model)
        for path in expanded_paths:
            gobject.idle_add(self.tree.expand_to_path, path)

        if isinstance(self, iPodPanel) and self.root:
            gobject.idle_add(self.tree.expand_row, self.model.get_path(self.root), False)
            gobject.idle_add(self.tree.expand_row, self.model.get_path(self.iroot), False)

class iPodPlaylist(object):
    """
        Container for iPod playlist
    """
    def __init__(self, playlist, root=False):
        """
            requires an gpod playlist object
        """
        self.playlist = playlist
        self.name = playlist.name
        self.root = root

    def __str__(self):
        """
            Returns the playlist name
        """
        return self.playlist.name

class iPodTransferQueue(gtk.VBox):
    """ 
        Shows tracks that are waiting to be transferred to the iPod
    """
    def __init__(self, panel):
        """
            Initializes the queue
        """
        gtk.VBox.__init__(self)
        self.panel = panel
        self.set_border_width(0)
        self.set_spacing(3)
        self.set_size_request(-1, 250)
        self.songs = []

        label = gtk.Label(_("Transfer Queue"))
        label.set_alignment(0, .50)
        self.pack_start(label, False, True)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        view = gtk.TreeView()
        scroll.add(view)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.list = xlmisc.ListBox(view)
        self.pack_start(scroll, True, True)

        self.progress = gtk.ProgressBar()
        self.pack_start(self.progress, False, False)

        buttons = gtk.HBox()
        buttons.set_spacing(3)
        self.clear = gtk.Button()
        image = gtk.Image()
        image.set_from_stock('gtk-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.clear.set_image(image)
        self.transfer = gtk.Button(_("Transfer"))
        buttons.pack_end(self.transfer, False, False)
        buttons.pack_end(self.clear, False, False)
        self.clear.connect('clicked',
            self.on_clear)
        self.transfer.connect('clicked', self.start_transfer)

        self.pack_start(buttons, False, False)
        targets = [('text/uri-list', 0, 0)]
        self.list.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, targets,
            gtk.gdk.ACTION_COPY)
        self.list.list.connect('drag_data_received', self.drag_data_received)

    def on_clear(self, widget):
        """
            Clears the queue
        """
        self.panel.queue = None
        self.hide()
        self.destroy()

    def start_transfer(self, widget):
        """
            Runs the transfer
        """
        self.itdb = self.panel.itdb
        count = 0
        songs = [song for song in self.list.rows]
        total = len(self.list.rows)
        for song in songs:
            track = song.ipod_track()
            cover = self.panel.get_cover_location(song)
            track.itdb = self.itdb
            if cover:
                gpod.itdb_track_set_thumbnails(track, cover)

            loc = str(song.loc)
            if song.type == 'podcast':
                loc = str(song.download_path)

            gpod.itdb_cp_track_to_ipod(track, loc, None)

            gpod.itdb_track_add(self.itdb, track, -1)
            mpl = gpod.itdb_playlist_mpl(self.itdb)
            if song.type == 'podcast':
                xlmisc.log("Using podcasts for %s" % song)
                mpl = gpod.itdb_playlist_podcasts(self.itdb)

            gpod.itdb_playlist_add_track(mpl, track, -1)
            if song.ipod_playlist and not \
                gpod.itdb_playlist_is_podcasts(song.ipod_playlist.playlist):
                gpod.itdb_playlist_add_track(song.ipod_playlist.playlist,
                    track, -1)
                song.ipod_playlist = None

            count += 1
            self.update_progress(song, float(count) /
                float(total))
            xlmisc.finish()

        self.panel.transferring = None
        xlmisc.finish()

        self.on_clear(None)
        self.panel.exaile.status.set_first(_("Writing iPod"
            " database..."))

        xlmisc.finish()
        gpod.itdb_write(self.itdb, None)
        self.panel.exaile.status.set_first(None)
        self.panel.load_tree()

    def update_progress(self, song, percent):
        """
            Updates the progress of the transfer
        """
        self.list.remove(song)
        self.progress.set_fraction(percent)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """ 
            Called when a track is dropped in the transfer queue
        """
        # just pass it on to the iPodPanel

        self.panel.drag_data_received(tv, context, x, y, selection, info,
            etime)

class iPodPropertiesDialog(object):
    """
        Shows information regarding the ipod
    """
    def __init__(self, exaile, panel):
        """
            Initializes the panel
        """
        self.exaile = exaile
        self.panel = panel
        xml = gtk.glade.XML("exaile.glade", "iPodPropertiesDialog", "exaile")
        self.dialog = xml.get_widget('iPodPropertiesDialog')
        self.image = xml.get_widget('ipod_properties_image')
        self.image.set_from_file('images%sipod.png' % os.sep)
        self.dialog.set_transient_for(exaile.window)
        self.progress = xml.get_widget('ipod_properties_progress')
        self.space_total = xml.get_widget('ipod_properties_space_total')
        self.space_used = xml.get_widget('ipod_properties_space_used')
        self.space_free = xml.get_widget('ipod_properties_space_free')
        self.model = xml.get_widget('ipod_properties_model')

        (type, total, used) = panel.get_space_info()
        model = panel.get_model()

        self.model.set_label(model)

        if type:
            self.space_total.set_label("%.1f%s total" % (total, type))
            self.space_used.set_label("%.1f%s used" % (used, type))
            free = total - used
            self.space_free.set_label("%.1f%s free" % (free, type))

            frac = used / total
            percent = int(frac * 100)
            self.progress.set_fraction(frac)
            self.progress.set_text("%s%%" % percent)

        self.dialog.show_all()
        self.dialog.run()
        self.dialog.destroy()

class iPodPanel(CollectionPanel):
    """
        Represents the entire ipod collection in a tree
    """
    name = 'ipod'
    def __init__(self, exaile):
        """
            Initializes the ipod collection panel. Expects a parent and exaile
            object
        """
        CollectionPanel.__init__(self, exaile)

        self.db = exaile.db
        self.ipod = True
        self.connected = False
        if not IPOD_AVAILABLE: return

        self.transfer_queue = None
        self.transferring = False
        self.write_lock = threading.Lock()
        self.queue = None
        self.ipod_track_count = self.xml.get_widget('ipod_track_count')

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            When tracks are dragged to this list
        """
        self.tree.unset_rows_drag_dest()
        self.tree.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.tree.targets, 
            gtk.gdk.ACTION_COPY)
        if not self.connected:
            common.error(self.exaile.window, _("Not connected to iPod"))
            return
        path = self.tree.get_path_at_pos(x, y)

        object = None
        if path:
            iter = self.model.get_iter(path[0])
            object = self.model.get_value(iter, 1)
        if isinstance(object, iPodPlaylist) and path:
            playlist = object
            xlmisc.log("Playlist %s" % playlist.name)
        else:
            playlist = None

        loc = selection.get_uris()
        songs = tracks.TrackData()
        update = False
        for url in loc:
            url = urllib.unquote(url)
            if url.find("ipod://") > -1:
                if not playlist: continue
                update = True
                song = self.get_song(url.replace("ipod://", ""))
                gpod.itdb_playlist_add_track(playlist.playlist,
                    song.ipod_track(), -1)
                playlist_id = tracks.get_column_id(self.db, 'playlist',
                    'name', playlist.name, True)
                path_id = tracks.get_column_id(self.db, 'paths', 'name',
                    song.loc, True)
                self.db.execute("REPLACE INTO playlist_items( playlist, path)"
                    " VALUES( ?, ? )", (playlist_id, path_id))

            else:
                song = self.exaile.all_songs.for_path(url)
                # check to see if it's a podcast
                if not song:
                    song = self.exaile.radio_panel.get_podcast(url)

                if not song:
                     song = tracks.read_track(self.db, self.exaile.all_songs, url)
                     if not song: continue

                ipod_song = self.get_song_on_ipod(song)
                if ipod_song and playlist:
                    gpod.itdb_playlist_add_track(playlist.playlist,
                        ipod_song.ipod_track(), -1)
                    update = True
                else:
                    if not song: continue
                    songs.append(song)

        if songs:
            self.add_to_transfer_queue(songs, playlist)
        elif update:
            self.save_database(True)
    
    def add_to_transfer_queue(self, songs, playlist=None):
        """
            Adds the specified songs to the transfer queue
        """
        if self.transferring:
            common.error(self.exaile.window, _("There is a transfer in progress. "
                "Please wait for it to complete."))
            return
        if not self.queue:
            self.queue_box = self.xml.get_widget('ipod_queue_box')
            self.queue = iPodTransferQueue(self)
            self.queue_box.pack_start(self.queue, False, False)

        queue = self.queue.songs
        error = ""
        for song in songs:
            if self.get_song_on_ipod(song):
                error += "'%s' already on iPod\n" % str(song)
                continue

            if not song.loc.lower().endswith(".mp3") or song.type == 'stream':
                error += "'%s' is not a supported iPod format\n" % str(song)
                continue

            song.ipod_playlist = playlist
            queue.append(song)

        if error:
            common.scrolledMessageDialog(self.exaile.window,
                error, _("The following errors did occur"))

        self.queue.list.set_rows(queue)
        if queue:
            self.queue.show_all()
        else:
            self.queue.hide()
            self.queue.destroy()
            self.queue = None

    def create_ipod_menu(self, root=False):
        """
            Creates the ipod menu
        """
        self.ipod_menu = xlmisc.Menu()
        self.open = self.ipod_menu.append(_("Open Playlist"),
            self.open_playlist)

        if not root:
            self.rename = self.ipod_menu.append(_("Rename"),
                self.rename_playlist)
        self.rm_playlist = self.ipod_menu.append(_("Remove"),
            self.remove_playlist)
        self.create = self.ipod_menu.append(_("Create Playlist"),
            self.create_playlist)

        self.blacklist.set_sensitive(False)
        item = gtk.MenuItem(label=_("Update Covers"))
        item.show()
        item.connect('activate', self.update_covers)
        self.menu.insert(item, 2)
        if root:
            self.ipod_menu.append_separator()
            self.ipod_menu.append("Properties", self.ipod_properties)

    def ipod_properties(self, widget, event=None):
        """
            Shows the ipod properties dialog
        """
        iPodPropertiesDialog(self.exaile, self)

    def create_popup(self):
        """
            Creates the popup menu
        """
        CollectionPanel.create_popup(self)
        self.create_ipod_menu()

    def remove_playlist(self, item, event):
        """
            Removes a playlist from the ipod
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        for path in paths:
            iter = model.get_iter(path)
            playlist = model.get_value(iter, 1)

            dialog = gtk.MessageDialog(self.exaile.window, 
                gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
                _("Are you sure you want to permanently delete the selected"
                " playlist?"))
            result = dialog.run()
            dialog.destroy()
            if result == gtk.RESPONSE_YES:
                gpod.itdb_playlist_remove(playlist.playlist)
                playlist_id = tracks.get_column_id(self.db, 'playlists',
                    'name', playlist.name, True)
                self.db.execute("DELETE FROM playlists WHERE id=?",
                    (playlist_id,))
                self.db.execute("DELETE FROM playlist_items WHERE playlist=?",
                    (playlist_id,))
                if self.list_dict.has_key(playlist.name):
                    del self.list_dict[playlist.name]
                self.model.remove(iter) 
                self.save_database(False)
                self.tree.queue_draw()
            break

    def rename_playlist(self, item, event):
        """
            Renames a playlist on the ipod
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        for path in paths:
            iter = model.get_iter(path)
            playlist = model.get_value(iter, 1)

            dialog = xlmisc.TextEntryDialog(self.exaile.window, 
                _("Enter the new name for the playlist"), 
                _("Rename Playlist"))
            result = dialog.run()
            dialog.destroy()
            if result == gtk.RESPONSE_OK:
                name = str(dialog.get_value())
                self.db.execute("UPDATE playlists SET name=? WHERE name=?", 
                    (name, playlist.playlist.name))
                if self.list_dict.has_key(playlist.name):
                    del self.list_dict[playlist.name]
                playlist.playlist.name = name
                playlist.name = name
                self.list_dict[name] = playlist
                self.save_database()
                self.tree.queue_draw()

    def create_playlist(self, item, event):
        """
            Creates a new playlist on the ipod
        """
        dialog = xlmisc.TextEntryDialog(self.exaile.window, 
            _("Enter a name for the new playlist"), _("New Playlist"))
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_OK:
            name = str(dialog.get_value())
            playlist = gpod.itdb_playlist_new(name, False)
            self.lists.append(iPodPlaylist(playlist))
            gpod.itdb_playlist_add(self.itdb, playlist, -1)
            item = self.model.append(self.iroot, [self.iplaylist_image,
                iPodPlaylist(playlist)])
            playlist_id = tracks.get_column_id(self.db, 'playlists', 'name',
                name, True)
            self.list_dict[name] = playlist
            self.save_database(False)

    def open_playlist(self, tree=None, widget=None):
        """
            Opens the selected playlist
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        for path in paths:
            iter = self.model.get_iter(path)
            object = self.model.get_value(iter, 1)
            if isinstance(object, iPodPlaylist):
                self.load_playlist(object)

    def get_song_on_ipod(self, song, playlist=None):
        """
            Gets the song on the iPod
        """
        for s in self.all:
            if s.title != song.title:
                continue
            elif s.artist != song.artist:
                continue
            elif s.album != song.album:
                continue
            elif s.duration != song.duration:
                continue
            elif s.title != song.title:
                continue
            else:
                return s

        return None

    def save_database(self, reload=True):
        """
            Writes the itunes database
        """
        gobject.idle_add(self.exaile.status.set_first, 
            _("Writing iPod database..."))
        xlmisc.finish()
        if self.connected and self.itdb:
            gpod.itdb_write(self.itdb, None)

        gobject.idle_add(self.exaile.status.set_first, None)
        xlmisc.log("Done writing iTunes database")
        if reload: gobject.idle_add(self.load_tree, False, False)

    def remove_from_playlist(self, tracks, playlist):
        """
            Removes items from an iPod playlist
        """
        playlist = playlist.playlist
        playlist_id = tracks.get_column_id(self.db, 'playlists', 'name',
            playlist.name, True)
        for track in tracks:
            path_id = tracks.get_column_id(self.db, 'paths', 'name', 
                self.mount + track.ipod_path.replace(":", "/"))
            self.db.execute("DELETE FROM playlist_items WHERE playlist=? "
                "AND path=?", (playlist_id, path_id))

            gpod.itdb_playlist_remove_track(playlist, track)

    def delete_tracks(self, tracks):
        """
            Deletes tracks from the iPod
        """
        if not self.connected or not self.itdb: return

        for track in tracks:
            track = track.ipod_track()
            for playlist in gpod.sw_get_playlists(self.itdb):
                if gpod.itdb_playlist_contains_track(playlist, track):
                    gpod.itdb_playlist_remove_track(playlist, track)

            gpod.itdb_track_unlink(track)

    def append_covers_recursive(self, iter, add):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)

        while True:
            object = self.model.get_value(iter, 1)
            if self.model.iter_has_child(iter):
                self.append_covers_recursive(iter, add)
            elif isinstance(object, media.Track):
                add.append(object)
            iter = self.model.iter_next(iter)
            if not iter: break

    def update_covers(self, widget):
        """
            Updates all cover art on the iPod
        """

        dialog = gtk.MessageDialog(self.exaile.window, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("This action will write all album art in the Exaile database to"
            " your iPod (overwriting any existing album art).  Are you sure"
            " you want to continue?"))
        result = dialog.run()
        dialog.destroy()

        if result != gtk.RESPONSE_YES: return

        self.exaile.status.set_first(_("Updating covers on"
            " iPod..."))
        selection = self.tree.get_selection()
        (modle, paths) = selection.get_selected_rows()
        add = []
        for path in paths:
            iter = self.model.get_iter(path)
            object = self.model.get_value(iter, 1)

            if self.model.iter_has_child(iter):
                self.append_covers_recursive(iter, add)
                continue
            elif isinstance(object, media.Track):
                add.append(object)

        for track in add:
            cover = self.get_cover_location(track)
            if cover:
                gpod.itdb_track_set_thumbnails(track.ipod_track(), cover)
                xlmisc.log("Updated cover for %s by %s" % (track.title,
                    track.artist))

        xlmisc.finish()
        self.exaile.status.set_first(_("Writing iPod "
            "database..."))
        gpod.itdb_write(self.itdb, None)
        self.exaile.status.set_first(None)

    def load_playlist(self, playlist):
        """
            Loads a playlist from the iPod
        """
        tracks = xl.tracks.search_tracks(self.exaile.window, self.db, self.all, None,
            str(playlist))

        self.exaile.new_page(playlist.name, tracks)
        self.exaile.tracks.playlist = playlist

    def get_cover_location(self, track):
        """
            Gets the location of the album art
        """
        db = self.exaile.db
        cur = db.realcursor()
        cur.execute("SELECT image FROM tracks,albums,paths WHERE paths.name=?"
            " AND paths.id=tracks.path AND albums.id=tracks.album",
            (track.loc,))
        row = cur.fetchone()
        cur.close()
        if not row or row[0] == '': return None
        return "%s%scovers%s%s" % (self.exaile.get_settings_dir(), os.sep,
            os.sep, str(row[0]))

    # this code is derived from Listen code (http://listen-gnome.free.fr)
    # Thanks!
    def get_model(self):
        """
            Returns model information about the iPod
        """
        model = 'Unknown'
        path = os.path.join(self.mount, 'iPod_Control', 'Device', 'SysInfo')
        if os.path.isfile(path):
            h = open(path)
            for line in h:
                if line.split(':')[0] == 'boardHwSwInterfaceRev':
                    mcode = line.split(' ')[1]

                    if mcode == '0x00010000':
                        model = '1G'
                    elif mcode == '0x00020000':
                        model = '2G'
                    elif mcode == '0x00030001':
                        model = '3G'
                    elif mcode == '0x00040013':
                        model = '1G Mini'
                    elif mcode == '0x00050013':
                        model = '4G'
                    elif mcode == '0x00060000':
                        model = 'Photo'
                    elif mcode == '0x00060004':
                        model = 'Color'
                    elif mcode == '0x00070002':
                        model = '2G Mini'
                    elif mcode == '0x000B0005':
                        model = '5G'
                    elif mcode == '0x000C0005':
                        model = 'Nano'
                    elif mcode == '0x000C0006':
                        model = 'Nano'
                    else:
                        model = 'Unknown'
        return model

    def get_space_info(self):
        """
            Returns the total space and used space on the ipod
        """
        h = popen("df -h")
        lines = h[0].readlines()[1:]
        
        for line in lines:
            line = line.strip()
            (device, total, used, avail, percent, mountpoint) = \
                re.split("\s+", line)
            if mountpoint == self.mount:
                type = 'G'
                if total.find("M") > -1:
                    type = "M"

                total = float(total.replace(type, ''))
                used = float(used.replace(type, ''))
                return type, total, used

        return None, None, None

    def connect_ipod(self, event=None):
        """
            Connects to the iPod and loads all the tracks on it
        """
        if self.transferring:
            common.error(self.exaile.window, _("There is a transfer in progress. "
                "Please wait for it to complete."))
            return
        self.mount = self.exaile.settings.get("ipod_mount", "/media/ipod")
        self.mount = str(self.mount)
        self.itdb = gpod.itdb_parse(self.mount, None)

        self.exaile_dir = "%s/iPod_Control/exaile" % self.mount
        self.log_file = "%s/lastfm.log" % self.exaile_dir
        self.db = db.DBManager(":memory:")
        self.db.add_function_create(('THE_CUTTER', 1, tracks.the_cutter))
        self.db.import_sql("sql/db.sql")
        self.db.check_version("sql")
        self.lists = []
        self.list_dict = dict()
        self.all = xl.tracks.TrackData()

        if not self.itdb: 
            self.connected = False
            self.all = tracks.TrackData()
            self.ipod_track_count.set_label(_("Not connected"))
            if event and event != 'refresh':
                common.error(self.exaile.window, _("Error connecting to "
                    "iPod"))
            return False
        if not os.path.isdir(self.exaile_dir):
            os.mkdir(self.exaile_dir)
        for item in ('PATHS', 'ALBUMS', 'ARTISTS', 'PLAYLISTS'):
            setattr(tracks, 'IPOD_%s' % item, {})
        self.all = xl.tracks.TrackData()
        ## clear out ipod information from database
        self.db.execute("DELETE FROM tracks WHERE type=1")

        for playlist in gpod.sw_get_playlists(self.itdb):
            if playlist.type == 1:
                self.lists.insert(0, iPodPlaylist(playlist, True))
            else:
                self.lists.append(iPodPlaylist(playlist))
            self.list_dict[playlist.name] = playlist
            playlist_id = tracks.get_column_id(self.db, 'PLAYLISTS', 'name',
                playlist.name, True)
            for track in gpod.sw_get_playlist_tracks(playlist):
                loc = self.mount + track.ipod_path.replace(":", "/")
                path_id = tracks.get_column_id(self.db, 'paths', 'name', loc,
                    True)
                self.db.execute("REPLACE INTO playlist_items(playlist, path) "
                    "VALUES( ?, ? )", (playlist_id, path_id))

        left = []
        for i in range(10):
            left.append('?')
        left = ", ".join(left)
        for track in gpod.sw_get_tracks(self.itdb):
            loc = self.mount + track.ipod_path.replace(":", "/")
            try:
                loc = unicode(loc)

                path_id = tracks.get_column_id(self.db, 'paths', 'name', loc,
                    ipod=True)
                artist_id = tracks.get_column_id(self.db, 'artists', 'name', 
                    track.artist, ipod=True)
                album_id = tracks.get_album_id(self.db, artist_id, track.album, ipod=True)

                self.db.execute("INSERT INTO tracks(path, " \
                    "title, artist, album, track, length," \
                    "bitrate, genre, year, user_rating ) " \
                    "VALUES( %s ) " % left, 

                    (path_id,
                    unicode(track.title),
                    unicode(artist_id),
                    unicode(album_id),
                    unicode(track.track_nr),
                    unicode(track.tracklen / 1000),
                    unicode(track.bitrate),
                    unicode(track.genre),
                    unicode(track.year),
                    unicode(track.rating)))

                itrack = track
                track = xl.tracks.read_track(self.db, None, loc, True, True)
                   
                if not track: continue
                track.itrack = itrack
                
                self.all.append(track)

            except UnicodeDecodeError:
                traceback.print_exc()
                continue

        self.db.commit()
        self.connected = True
        if self.exaile.settings.get_boolean('as_submit_ipod', False):
            self.submit_tracks()

    def get_song(self, loc):
        """
            Returns a track for a location
        """
        return self.all.for_path(loc)

    def update_log(self):
        """
            Updating played tracks log on the iPod
        """
        xlmisc.log("Updating log...")
        try:
            handle = open(self.log_file, "w")
        except IOError:
            return
        for track in gpod.sw_get_tracks(self.itdb):
            if track.playcount:
                handle.write("%d\t%d\t%d\t%d\n" % (track.id, track.playcount,
                    track.playcount2, track.time_played))

        handle.close()

    def submit_tracks(self):
        """
            Submits tracks that have been played on the iPod since the last
            log update
        """
        user = self.exaile.settings.get('lastfm_user', '')
        password = self.exaile.settings.get('lastfm_pass', '')
        if not user or not password: return

        xlmisc.log("Submitting tracks from iPod...")
        info = dict()

        try:
            handle = open(self.log_file)
            for line in handle.readlines():
                line = line.strip()
                (id, playcount, p2, played) = line.split("\t")
                info[id] = played


            handle.close()
        except IOError:
            pass

        scrobbler = xl.media.get_scrobbler_session()
        if not scrobbler: return
        tracks = dict()

        for track in gpod.sw_get_tracks(self.itdb):
            if (not str(track.id) in info and
                track.playcount > 0) or (str(track.id) in info and
                str(track.time_played) != info[str(track.id)]):

                tracks[float(str(track.time_played) + "." + 
                    str(track.id))] = track

        submit = []
        keys = tracks.keys()
        keys.sort()
        for key in keys:
            track = tracks[key]
            lt = time.localtime(track.time_played - 2082845972)
            date = "%02d-%02d-%02d %02d:%02d:%02d" % (lt[0], lt[1], lt[2],
                lt[3], lt[4], lt[5])
            xlmisc.log("submitting %s by %s played %s" % (track.title, track.artist,
                date))
            submit.append(track)

        if not len(submit):
            xlmisc.log("No tracks to submit.")
            return

        thread.start_new_thread(self.submit, (scrobbler, submit))
        self.update_log()
        xlmisc.log("All tracks have been submitted from iPod, log has been updated.")

    def submit(self, scrobbler, submit):
        """
            Submits played tracks to Last.fm
        """
        for track in submit:
            lt = time.localtime(track.time_played - 2082845972)
            date = "%02d-%02d-%02d %02d:%02d:%02d" % (lt[0], lt[1], lt[2],
                lt[3], lt[4], lt[5])
            try:
                scrobbler(artist_name=track.artist,
                    song_title=track.title,
                    length=track.tracklen / 1000,
                    date_played=date,
                    album=track.album)
            except:
                xlmisc.log_exception()

    def load_tree(self, event=None, connect=True):
        """
            Loads the tree (and connects to the ipod if refresh was pressed)
        """
        if connect: self.connect_ipod(event)
        xlmisc.log("Loading iPod collection tree")
        CollectionPanel.load_tree(self, event)
        self.ipod_track_count.set_label("%d tracks" % len(self.all))
        if not self.connected:
            self.ipod_track_count.set_label(_("Not connected"))

class SmartPlaylist(object):
    def __init__(self, name, id):
        self.name = name
        self.id = id

    def __str__(self):
        return self.name

class BuiltinPlaylist(object):
    def __init__(self, name, sql):
        self.name = name
        self.sql = sql

    def __str__(self):
        return self.name

class CustomPlaylist(object):
    def __init__(self, name, id):
        self.name = name
        self.id = id

    def __str__(self):
        return self.name

class PlaylistsPanel(object):
    """ 
        The playlists panel 
    """
    SMART_PLAYLISTS = ("Entire Library", "Highest Rated", "Top 100", "Most Played",
        "Least Played", "Random 100", "Rating > 5", "Rating > 3", "Newest 100")

    def __init__(self, exaile):
        """
            Creates the playlist panel
        """
        self.exaile = exaile
        self.db = self.exaile.db
        self.xml = exaile.xml
        container = self.xml.get_widget('playlists_box')

        self.targets = [('text/uri-list', 0, 0)]
        self.tree = xlmisc.DragTreeView(self, True, False)
        self.tree.connect('row-activated', self.open_playlist)
        self.tree.set_headers_visible(False)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(self.scroll, True, True)
        container.show_all()
        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)

        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)

        self.tree.set_model(self.model)
        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.playlist_image = gtk.gdk.pixbuf_new_from_file('images%splaylist.png' % os.sep)
        self.smart = self.model.append(None, [self.open_folder, _("Smart"
            " Playlists"), None])
        self.smart_dict = {
            'Entire Library': "SELECT paths.name FROM artists, albums, tracks, paths WHERE " \
                "paths.id=tracks.path AND artists.id=tracks.artist AND " \
                "albums.id=tracks.albums ORDER BY LOWER(artists.name), " \
                "THE_CUTTER(albums.name)",

            'Top 100': "SELECT paths.name FROM tracks,paths WHERE " \
                "paths.id=tracks.path ORDER BY rating " \
                "DESC LIMIT 100",

            'Highest Rated': "SELECT paths.name FROM tracks,paths WHERE " \
                "tracks.path=paths.id " \
                "ORDER BY user_rating DESC " \
                "LIMIT 100",

            'Most Played': "SELECT paths.name FROM paths, tracks WHERE " \
                "tracks.path=paths.id ORDER " \
                "BY plays DESC LIMIT 100",

            'Least Played': "SELECT paths.name FROM paths, tracks WHERE " \
                "paths.id=tracks.path ORDER " \
                "BY plays ASC LIMIT 100",

            'Rating > 5': "SELECT paths.name FROM paths, tracks, artists, " \
                "albums " \
                "WHERE tracks.path=paths.id AND albums.id=tracks.album AND " \
                "artists.id=tracks.artist " \
                "AND user_rating > 5 " \
                "ORDER BY LOWER(artists.name), THE_CUTTER(albums.name), track",
            
            'Rating > 3': "SELECT paths.name FROM paths,tracks,artists,albums WHERE " \
                "tracks.path=paths.id AND albums.id=tracks.album AND " \
                "artists.id=tracks.artist AND user_rating > 3 " \
                "ORDER BY LOWER(artists.name), LOWER(albums.name), track", 

            'Newest 100': "SELECT paths.name FROM paths,tracks WHERE " \
                "tracks.path=paths.id AND time_added!='' " \
                "ORDER BY time_added DESC " \
                "LIMIT 100",

            'Random 100': "SELECT paths.name FROM tracks,paths WHERE " \
                "paths.id=tracks.path"
        }

        self.model.append(self.smart, [self.playlist_image, 'Entire Library',
            BuiltinPlaylist('Entire Library', self.smart_dict[
            'Entire Library'])])

        self.builtin = self.model.append(self.smart, [self.open_folder,
            'Built In', None])

        items = ('Top 100', 'Highest Rated', 'Most Played',
            'Least Played', 'Rating > 5', 'Rating > 3', 'Newest 100', 'Random'
            ' 100')

        for name in items:
            sql = self.smart_dict[name]
            self.model.append(self.builtin, [self.playlist_image, name, 
                BuiltinPlaylist(name, sql)]) 
        
        self.custom = self.model.append(None, [self.open_folder,
            _("Custom Playlists"), None])
        
        self.tree.expand_all()
        self.setup_menu()

    def setup_menu(self):
        """ 
            Sets up the popup menu for the playlist tree
        """
        self.menu = xlmisc.Menu()
        self.menu.append('Add Playlist', self.on_add_playlist, 'gtk-add')
        self.menu.append('Add Smart Playlist', self.on_add_smart_playlist, 
            'gtk-add')
        self.menu.append_separator()
        self.remove_item = self.menu.append('Delete Playlist', 
            self.remove_playlist,
            'gtk-remove')

    def on_add_smart_playlist(self, widget, event):
        """
            Adds a smart playlist
        """
        dialog = filtergui.FilterDialog('Add Smart Playlist', CRITERIA)

        dialog.set_transient_for(self.exaile.window)
        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_ACCEPT:
            name = dialog.get_name()
            if not name: 
                common.error(self.exaile.window, _("You did not enter a "
                    "name for your playlist"))
                return
            row = self.db.read_one('playlists', 'name', 'name=?', (name,))
            if row:
                common.error(self.exaile.window, _("That playlist name "
                    "is already taken."))
                return

            self.db.execute("INSERT INTO playlists( name, type ) VALUES( "
                " ?, 1 )", (name,))
            row = self.db.read_one('playlists', 'id', 'name=?', (name,))
            playlist_id = row[0]

            count = 0
            for c, v in dialog.get_state():
                if type(v) != list:
                    v = list((v,))
                self.db.execute("INSERT INTO smart_playlist_items( "
                    "playlist, line, crit1, crit2, filter ) VALUES( "
                    " ?, ?, ?, ?, ? )", (playlist_id, count, c[0], c[1],
                    repr(v)))
                count += 1

            self.db.commit()

            self.model.append(self.smart, [self.playlist_image, name, 
                SmartPlaylist(name, playlist_id)])

        dialog.destroy()

    def button_press(self, widget, event):
        """
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)
        delete_enabled = False
        if self.tree.get_path_at_pos(x, y):
            (path, col, x, y) = self.tree.get_path_at_pos(x, y)
            iter = self.model.get_iter(path)
            obj = self.model.get_value(iter, 2)
            if isinstance(obj, CustomPlaylist) or \
                isinstance(obj, SmartPlaylist):
                delete_enabled = True

        self.remove_item.set_sensitive(delete_enabled)

        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)

    def open_playlist(self, tree, path, col):
        """
            Called when the user double clicks on a tree item
        """
        iter = self.model.get_iter(path)
        obj = self.model.get_value(iter, 2)
        if isinstance(obj, BuiltinPlaylist):
            name = obj.name
            sql = obj.sql

            if name == 'Entire Library':    
                songs = self.exaile.all_songs
            elif name == 'Random 100':
                songs = tracks.TrackData()
                for song in self.exaile.all_songs:
                    songs.append(song)

                random.shuffle(songs)
                songs = tracks.TrackData(songs[:100])
            else:
                songs = xl.tracks.search_tracks(self.exaile.window, 
                    self.db,
                    self.exaile.all_songs, None, None, sql)

            self.exaile.new_page(name, songs)

        elif isinstance(obj, SmartPlaylist):
            self.open_smart_playlist(obj.name, obj.id)

        elif isinstance(obj, CustomPlaylist):
            playlist = obj.name
            self.playlist_songs = xl.tracks.search_tracks(self, self.db,
                self.exaile.all_songs, None, playlist)
            self.exaile.new_page(playlist, self.playlist_songs)
            self.exaile.on_search()
            self.exaile.tracks.playlist = playlist

    def open_smart_playlist(self, name, id):
        """
            Opens a smart playlist
        """
        rows = self.db.select("SELECT crit1, crit2, filter FROM "
            "smart_playlist_items WHERE playlist=? ORDER BY line", (id,))

        where = []
        andor = " AND "
        for row in rows:
            print row
            sql = get_sql(row[0], row[1], row[2])
            if sql:
                where.append(sql)

        sql = """
            SELECT paths.name 
                FROM tracks,paths,artists,albums 
            WHERE 
                (
                    paths.id=tracks.path AND 
                    artists.id=tracks.artist AND 
                    albums.id=tracks.album
                ) 
                AND (%s) 
                ORDER BY 
                    LOWER(artists.name),
                    THE_CUTTER(albums.name), 
                    track, title
            """ % andor.join(where)
        xlmisc.log(sql)
        songs = xl.tracks.search_tracks(self.exaile.window,
            self.db, self.exaile.all_songs, None, None, sql)

        self.exaile.new_page(name, songs)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags tracks to the smart playlists panel
        """
        path = self.tree.get_path_at_pos(x, y)
        error = ""
        if path: 
            iter = self.model.get_iter(path[0])
            obj = self.model.get_value(iter, 2)
        else:
            obj = None

        uris = selection.get_uris()
        songs = tracks.TrackData()
        for l in uris:
            l = urllib.unquote(l)
            if l.find("ipod://") > -1:
                error += "Could not add ipod track \"%s\" to library " \
                    "playlist\n" % l
            else:
                song = self.exaile.all_songs.for_path(l)
                if song: songs.append(song)

        if not isinstance(obj, CustomPlaylist): 
            self.on_add_playlist(self.remove_item, items=songs)
            return

        xlmisc.log("Adding tracks to playlist %s" % obj.name)
        if error:
            common.scrolledMessageDialog(self.exaile.window,
                error, _("The following errors did occur"))

        self.add_items_to_playlist(obj.name, songs)

    def remove_playlist(self, item, event):
        """
            Asks if the user really wants to delete the selected playlist, and
            then does so if they choose 'Yes'
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()

        obj = model.get_value(iter, 2)
        if not isinstance(obj, CustomPlaylist) or \
            not isinstance(obj, SmartPlaylist): return

        dialog = gtk.MessageDialog(self.exaile.window, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("Are you sure you want to permanently delete the selected"
            " playlist?"))
        if dialog.run() == gtk.RESPONSE_YES:
            playlist = obj.name 
            p_id = tracks.get_column_id(self.db, 'playlists', 'name', playlist)
            self.db.execute("DELETE FROM playlists WHERE id=?", (p_id,))

            table = 'playlist_items'
            if isinstance(obj, SmartPlaylist):
                table = 'smart_playlist_items':
            self.db.execute("DELETE FROM %s WHERE playlist=?" % table,
                (p_id,))
            if tracks.PLAYLISTS.has_key(playlist):
                del tracks.PLAYLISTS[playlist]
            self.db.commit()
            
            self.model.remove(iter)
        dialog.destroy()

    def load_playlists(self):
        """
            Loads all playlists and adds them to the list
        """
        rows = self.db.select("SELECT name, id, type FROM playlists ORDER BY"
            " name")
        for row in rows:
            if not row[2]:
                self.model.append(self.custom, [self.playlist_image, row[0],
                    CustomPlaylist(row[0], row[1])])
            elif row[2] == 1:
                self.model.append(self.smart, [self.playlist_image, row[0],
                    SmartPlaylist(row[0], row[1])])
        self.tree.expand_all()

    def on_add_playlist(self, widget, event=None, items=None):
        """
            Adds a playlist to the database
        """
        dialog = xlmisc.TextEntryDialog(self.exaile.window, 
            _("Enter the name you want for your new playlist"),
            _("New Playlist"))
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if name == "": return None
            c = self.db.record_count("playlists", "name=?", (name,))

            if c > 0:
                common.error(self.exaile.window, _("Playlist already exists."))
                return name

            playlist_id = tracks.get_column_id(self.db, 'playlists', 'name',
                name)
                
            self.model.append(self.custom, [self.playlist_image, name,
                CustomPlaylist(name, playlist_id)])
            self.tree.expand_all()

            if type(widget) == gtk.MenuItem:
                self.add_items_to_playlist(name, items)
            return name
        else: return None

    def add_items_to_playlist(self, playlist, songs=None):
        """
            Adds the selected tracks tot he playlist
        """
        if type(playlist) == gtk.MenuItem:
            playlist = playlist.get_child().get_label()

        if songs == None: songs = self.exaile.tracks.get_selected_tracks()
        playlist_id = tracks.get_column_id(self.db, 'playlists', 'name', playlist)

        for track in songs:
            if isinstance(track, media.StreamTrack): continue
            path_id = tracks.get_column_id(self.db, 'paths', 'name', track.loc)
            self.db.execute("INSERT INTO playlist_items( playlist, path ) " \
                "VALUES( ?, ? )", (playlist_id, path_id))
        self.db.commit()

class CustomWrapper(object):
    """
        Wraps a custom radio station
    """
    def __init__(self, name):
        """
            initializes the wrapper
        """
        self.name = name

    def __str__(self):
        """
            Returns the name
        """
        return self.name

class PodcastWrapper(object):
    """
        Wraps a podcast
    """
    def __init__(self, name, path):
        """
            Initializes the wrapper
        """
        self.name = name
        self.path = path

    def __str__(self):
        """
            Returns the name
        """
        return self.name

class PodcastQueueThread(threading.Thread):
    """
        Downloads podcasts in the queue one by one
    """
    def __init__(self, transfer_queue, panel):
        """ 
            Initializes the transfer
        """
        threading.Thread.__init__(self)
        self.transfer_queue = transfer_queue
        self.panel = panel
        self.queue = transfer_queue.queue
        self.stopped = False

    def run(self):
        """
            Actually runs the thread
        """
        for song in self.queue: 
            (download_path, downloaded) = \
                self.panel.get_podcast_download_path(song.loc)
            if self.stopped: break
            hin = urllib.urlopen(song.loc)

            temp_path = "%s%spodcasts%sdownloading" % \
                (self.panel.exaile.get_settings_dir(), os.sep, os.sep)
            hout = open(temp_path, "w+")

            count = 0
            while True:
                data = hin.read(1024)
                self.transfer_queue.downloaded_bytes += len(data)
                if count >= 10:
                    gobject.idle_add(self.transfer_queue.update_progress)
                    count = 0
                if not data: break
                hout.write(data)
                if self.stopped:
                    hout.close()
                    os.unlink(temp_path)
                    break

                count += 1

            hin.close()
            hout.close()

            if os.path.isfile(temp_path):
                os.rename(temp_path, download_path)
            if self.stopped: break

            self.transfer_queue.downloaded += 1
            gobject.idle_add(self.transfer_queue.update_progress)
            song.download_path = download_path
            temp = tracks.read_track(None, None, download_path, False, False,
                False)

            if temp:
                song.set_len(temp.duration)
                self.db = self.panel.exaile.db
                self.panel.exaile.db.execute(
                    "UPDATE podcast_items SET length=%s WHERE podcast_path=%s"
                    " AND path=%s" % (self.db.p, self.db.p, self.db.p), 
                    (temp.duration, song.podcast_path, song.loc))
                self.panel.exaile.db.commit()
                if song.podcast_artist:
                    song.artist = song.podcast_artist

            gobject.idle_add(self.transfer_queue.update_song, song)
            xlmisc.log("Downloaded podcast %s" % song.loc)

        gobject.idle_add(self.transfer_queue.die)

class PodcastTransferQueue(gtk.VBox):
    """
        Represents the podcasts that should be downloaded
    """
    def __init__(self, panel):
        """
            Starts the transfer queue
        """
        gtk.VBox.__init__(self)
        self.panel = panel

        self.label = gtk.Label(_("Downloading Podcasts"))
        self.label.set_alignment(0, 0)

        self.pack_start(self.label)
        self.progress = gtk.ProgressBar()
        self.progress.set_text(_("Downloading..."))
        self.progress.set_size_request(-1, 24)
        
        vert = gtk.HBox()
        vert.set_spacing(3)
        vert.pack_start(self.progress, True, True)
        
        button = gtk.Button()
        image = gtk.Image()
        image.set_from_stock('gtk-stop', 
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        button.set_image(image)
        button.set_size_request(32, 32)

        vert.pack_end(button, False, False)
        button.connect('clicked', self.stop)

        self.pack_start(vert)

        self.downloaded = 0
        self.downloaded_bytes = 0
        self.total = 0
        self.total_bytes = 0
        self.queue = tracks.TrackData()
        self.queue_thread = None
        panel.podcast_download_box.pack_start(self)
        self.show_all()

    def stop(self, widget):
        """
            Stops the download queue
        """
        if self.queue_thread:
            self.queue_thread.stopped = True

        self.label.set_label(_("Stopping..."))

    def update_song(self, song):
        """ 
            Updates song information in the display
        """
        nb = self.panel.exaile.playlists_nb
        for i in range(nb.get_n_pages()):
            page = nb.get_nth_page(i)
            if isinstance(page, trackslist.TracksListCtrl):
                for item in page.songs:
                    if item == song:
                        page.refresh_row(song)

    def update_progress(self):
        """ 
            Update the progress bar with the percent of downloaded items
        """
        if self.total_bytes:
            total = float(self.total_bytes)
            down = float(self.downloaded_bytes)
            percent = down / total
            self.progress.set_fraction(percent)

        self.label.set_label("%d of %d downloaded" % (self.downloaded,
            self.total))

    def append(self, song):
        """
            Appends an item to the queue
        """
        self.queue.append(song)
        self.total += 1
        self.total_bytes += song.size
        self.update_progress()
        if not self.queue_thread:
            self.queue_thread = PodcastQueueThread(self, self.panel)
            self.queue_thread.start()

    def die(self):
        """
            Removes the download queue
        """
        self.hide()
        self.panel.podcast_download_box.remove(self)
        self.panel.podcast_queue = None

class RadioPanel(object):
    """
        Displays a list of saved radio stations, and scans shoutcast for a
        list of their available radio stations.
    """
    genres = (
            ('Alternative', ('College', 'Industrial', 'Punk', 'Hardcore',
                'Ska')),
            ('Americana', ('Blues', 'Folk', 'Cajun', 'Bluegrass')),
            ('Classical', ('Contemporary', 'Opera', 'Symphonic')),
            ('Country', ('Western Swing', 'New Country', 'Bluegrass')),
            ('Electronic', ('Ambient', 'Drum and Bass', 'Trance', 'Techno',
                'House', 'Downtempo', 'Breakbeat', 'Acid Jazz')),
            ('Hip Hop', ('Hardcore', 'Alternative', 'Turntablism', 'Old School',
                'New School')),
            ('Jazz', ('Latin', 'Swing', 'Big Band', 'Classic', 'Smooth',
                'Acid Jazz')),
            ('Pop/Rock', ('Oldies', 'Classic', '80s', 'Top 40', 'Metal',
                'Rock', 'Pop')),
            ('R&B/Soul', ('Contemporary', 'Classic', 'Funk', 'Smooth',
                'Urban')),
            ('Spiritual', ('Pop', 'Rock', 'Alternative', 'Gospel', 'Country')),
            ('Spoken', ('Talk', 'Comedy', 'Spoken Word')),
            ('World', ('Reggae/Island', 'African', 'Latin', 'European',
                'Middle Easern', 'Asian')),
            ('Other/Mixed', ('Eclectic', 'Film/Show', 'Instrumental'))
        )
    def __init__(self, exaile):
        """
            Initializes the panel and lays out the components
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = exaile.xml
        self.tree = self.xml.get_widget('radio_tree')
        icon = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn('radio')
        col.pack_start(icon)
        col.pack_start(text)
        col.set_attributes(icon, pixbuf=0)
        col.set_cell_data_func(text, self.cell_data_func)
        self.tree.append_column(col)
        self.podcasts = {}

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.tree.set_model(self.model)

        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.folder = xlmisc.get_icon('gnome-fs-directory')

        self.track = gtk.gdk.pixbuf_new_from_file('images%strack.png' %
            os.sep)
        self.custom = self.model.append(None, [self.open_folder, "Saved Stations"])
        self.podcast = self.model.append(None, [self.open_folder, "Podcasts"])

        # load all saved stations from the database
        rows = self.db.select("SELECT name FROM radio "
            "ORDER BY name")
        for row in rows:
            self.model.append(self.custom, [self.track, CustomWrapper(row[0])])

        # load podcasts
        rows = self.db.select("SELECT title, paths.name FROM podcasts,paths "
            "WHERE paths.id=podcasts.path")
        for row in rows:
            title = row[0]
            path = row[1]
            if not title: title = path
            self.model.append(self.podcast, [self.track, 
                PodcastWrapper(title, path)])

        # create the shoutcast tree
        sc = self.model.append(None, [self.open_folder, _("Shoutcast Stations")])
        for genre in self.genres:
            
            node = self.model.append(sc, [self.folder, genre[0]])
            for sub in genre[1]:
                self.model.append(node, [self.track, sub])

        self.tree.expand_row(self.model.get_path(self.custom), False)
        self.tree.expand_row(self.model.get_path(self.podcast), False)
        self.tree.expand_row(self.model.get_path(sc), False)
        self.tree.queue_draw()
        self.tree.connect('row-expanded', self.on_expanded)
        self.tree.connect('row-collapsed', self.on_collapsed)
        self.tree.connect('button-press-event', self.button_pressed)
        self.tree.connect('button-release-event', self.button_release)
        self.__dragging = False
        self.xml.get_widget('radio_add_button').connect('clicked',
            self.on_add_station)
        self.xml.get_widget('radio_remove_button').connect('clicked',
            self.remove_station)
        self.podcast_download_box = \
            self.xml.get_widget('podcast_download_box')
        self.podcast_queue = None
        self.setup_menus()

    def button_release(self, widget, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.__dragging: return True
        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True
        selection = self.tree.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.tree.get_path_at_pos(x, y)
        if not path: return False
        selection.unselect_all()
        selection.select_path(path[0])

    def button_pressed(self, widget, event):
        """
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        selection.unselect_all()
        (x, y) = event.get_coords()
        x = int(x); y = int(y)
        if not self.tree.get_path_at_pos(x, y): return
        (path, col, x, y) = self.tree.get_path_at_pos(x, y)
        selection.select_path(path)
        model = self.model
        iter = model.get_iter(path)
        
        object = model.get_value(iter, 1)
        if event.button == 3:
            # if it's for podcasts
            if isinstance(object, PodcastWrapper) or \
                object == "Podcasts":
                self.podmenu.popup(None, None, None,
                    event.button, event.time)
                return

            if model.iter_has_child(iter): return
            if isinstance(object, CustomWrapper):
                self.cmenu.popup(None, None, None,
                    event.button, event.time)
            else:
                if object == "Saved Stations" or \
                    object == "Podcasts" or \
                    object == "Shoutcast Stations":
                    return
                self.menu.popup(None, None, None,
                    event.button, event.time)
            
        elif event.type == gtk.gdk._2BUTTON_PRESS:

            if model.iter_has_child(iter):
                path = self.model.get_path(iter)
                self.tree.expand_row(path, False)
                return

            if isinstance(object, CustomWrapper):
                self.open_station(object.name)
            elif isinstance(object, PodcastWrapper):
                self.open_podcast(object)
            else:
                self.fetch_streams()

    def open_podcast(self, wrapper):
        """
            Opens a podcast
        """
        podcast_path_id = tracks.get_column_id(self.db, 'paths', 'name',
            wrapper.path)

        xlmisc.log("Opening podcast %s" % wrapper.name)
        row = self.db.read_one("podcasts", "description", "path=?", 
            (podcast_path_id, ))
        if not row: return

        desc = row[0]
        rows = self.db.select("SELECT paths.name, title, description, length, "
            "pub_date, size FROM podcast_items, paths WHERE podcast_path=? "
            "AND paths.id=podcast_items.path ORDER BY"
            " pub_date DESC LIMIT 10", 
            (podcast_path_id,))

        songs = tracks.TrackData()
        for row in rows:
            t = common.strdate_to_time(row[4])
            year = time.strftime("%x", time.localtime(t))
            info = ({
                'title': row[1],
                'artist': row[2],
                'album': desc,
                'url': row[0],
                'year': row[4], 
                'length': row[3], 
                'size': row[5]
            })

            (download_path, downloaded) = \
                self.get_podcast_download_path(row[0])
            add_item = False
            if not downloaded:
                info['artist'] = "Not downloaded"
                info['download_path'] = ''
                add_item = True
            else:
                info['download_path'] = download_path

            song = media.PodcastTrack(info)
            song.length = row[3]
            song.podcast_path = wrapper.path
            songs.append(song)
            self.podcasts[song.url] = song
            if add_item:
                song.podcast_artist = row[2] 
                self.add_podcast_to_queue(song)
            else:
                song.podcast_artist = None

        self.exaile.new_page(str(wrapper), songs)

    def get_podcast(self, url):
        """
            Returns the podcast for the specified url
        """
        if self.podcasts.has_key(url):
            return self.podcasts[url]
        else: return None

    def add_podcast_to_queue(self, song):
        """
            Add to podcast transfer queue
        """
        if not self.podcast_queue:
            self.podcast_queue = PodcastTransferQueue(self)

        if not song.loc in self.podcast_queue.queue.paths:
            self.podcast_queue.append(song)

    def get_podcast_download_path(self, loc):
        """
            Gets the location of the downloaded pocast item
        """
        (path, ext) = os.path.splitext(loc)
        hash = md5.new(loc).hexdigest()
        savepath = "%s%s%s" % (self.exaile.get_settings_dir(),
            os.sep, 'podcasts')
        if not os.path.isdir(savepath):
            os.mkdir(savepath, 0777)

        file = "%s%s%s%s" % (savepath, os.sep, hash, ext)
        if os.path.isfile(file): return file, True
        else: return file, False

    def cell_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, CustomWrapper):
            cell.set_property('text', str(object))
        else:
            cell.set_property('text', str(object))
            
    def on_collapsed(self, tree, iter, path):
        """
            Called when someone collapses a tree item
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.model.set_value(iter, 0, self.folder)
        self.tree.queue_draw()

    def on_expanded(self, tree, iter, path):
        """
            Called when someone collapses a tree item
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.model.set_value(iter, 0, self.open_folder)
        self.tree.queue_draw()

    def setup_menus(self):
        """
            Create the two different popup menus associated with this tree.
            There are two menus, one for saved stations, and one for
            shoutcast stations
        """
        self.menu = xlmisc.Menu()
        rel = self.menu.append(_("Reload Streams"), lambda e, f:
            self.fetch_streams(True))

        # custom playlist menu
        self.cmenu = xlmisc.Menu()
        self.add = self.cmenu.append(_("Add Stream to Station"), 
            self.add_url_to_station)
        self.delete = self.cmenu.append(_("Delete this Station"),
            self.remove_station)

        self.podmenu = xlmisc.Menu()
        self.podmenu.append(_("Add Feed"), self.on_add_podcast)
        self.podmenu.append(_("Refresh Feed"), self.refresh_feed)
        self.podmenu.append(_("Delete Feed"), self.delete_podcast)

    def refresh_feed(self, widget, event):
        """
            Refreshes a feed
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        if isinstance(object, PodcastWrapper):
            self.refresh_podcast(object.path, iter)

    def on_add_podcast(self, widget, event):
        """
            Called when a request to add a podcast is made
        """
        dialog = xlmisc.TextEntryDialog(self.exaile.window, _("Enter the location of"
            " the podcast"), _("Add a podcast"))

        if dialog.run() == gtk.RESPONSE_OK:
            name = dialog.get_value()
            dialog.destroy()
            path_id = tracks.get_column_id(self.db, 'paths', 'name', name)
            if self.db.record_count("podcasts", "path=?", (name, )):
                common.error(self.exaile.window, 
                    _("A podcast with that url already"
                    " exists"))
                return

            self.db.execute("INSERT INTO podcasts( path ) VALUES( ? )",
                (path_id,))
            self.db.commit()

            item = self.model.append(self.podcast,
                [self.track, PodcastWrapper("Fetching...", name)])
            self.tree.expand_row(self.model.get_path(self.podcast), False)

            self.refresh_podcast(name, item)
        dialog.destroy()

    def refresh_podcast(self, path, item):
        """
            Refreshes a podcast
        """
        thread = xlmisc.ThreadRunner(self.fetch_podcast_xml)
        thread.path = path
        thread.item = item
        thread.start()

    def fetch_podcast_xml(self, thread):
        """
            Fetches the podcast xml
        """
        path = thread.path
        item = thread.item
        try:
            h = urllib.urlopen(path)
            xml = h.read()
            h.close()
        except IOError:
            gobject.idle_add(common.error, self.exaile.window, 
                _("Could not read feed."))
            return

        gobject.idle_add(self.parse_podcast_xml, path, item, xml)

    def parse_podcast_xml(self, path, iter, xml):
        """
            Parses the xml from the podcast and stores the information to the
            database
        """
        path = str(path)
        xml = minidom.parseString(xml).documentElement
        root = xml.getElementsByTagName('channel')[0]

        title = self.get_val(root, 'title')
        description = self.get_val(root, 'description')
        if not description: description = ""
        pub_date = self.get_val(root, 'pubDate')
        print pub_date
        if not pub_date: pub_date = ""
        image = self.get_val(root, 'image')
        if not image: image = ""
        path_id = tracks.get_column_id(self.db, 'paths', 'name', path)

        self.db.execute("UPDATE podcasts SET title=?, "
            "pub_date=?, description=?, image=? WHERE"
            " path=?", (title, pub_date, description, image, path_id))

        self.model.set_value(iter, 1, PodcastWrapper(title, path))
        root_title = title
        items = root.getElementsByTagName('item')

        for item in items:
            title = self.get_val(item, 'title')
            link = self.get_val(item, 'link')
            print title, link
            desc = self.get_val(item, 'description')

            desc = self.clean_desc(desc)
            enc = self.get_child(item, 'enclosure')
            date = self.get_val(item, 'pubDate')
            if enc:
                size = enc[0].getAttribute('length')
                length = enc[0].getAttribute('duration')
                loc = str(enc[0].getAttribute("url"))
            else: continue
            loc_id = tracks.get_column_id(self.db, 'paths', 'name', loc)

            row = self.db.read_one("podcast_items", "path", 
                "podcast_path=? AND path=?", (path_id, loc_id))

            t = common.strdate_to_time(date)
            date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

            self.db.update("podcast_items",
                {
                    "podcast_path": path_id,
                    "path": loc_id,
                    "pub_date": date,
                    "description": desc,
                    "size": size,
                    "title": title,
                    "length": length,
                }, "path=? AND podcast_path=?", 
                (loc_id, path_id), row == None)

        self.db.commit()

        gobject.timeout_add(500, self.open_podcast, PodcastWrapper(root_title, path))

    def clean_desc(self, desc):
        """ 
            Cleans description of html, and shortens it to 70 chars
        """
        reg = re.compile("<[^>]*>", re.IGNORECASE|re.DOTALL)
        desc = reg.sub('', desc)
        reg = re.compile("\n", re.IGNORECASE|re.DOTALL)
        desc = reg.sub('', desc)

        desc = re.sub("\s+", " ", desc)

        if len(desc) > 70: add = "..."
        else: add = ''

        desc = desc[:70] + add
        return desc

    def get_child(self, node, name):
        """ 
            Gets a child node
        """
        return node.getElementsByTagName(name)

    def get_value(self, node):
        if hasattr(node, "firstChild") and node.firstChild:
            return node.firstChild.nodeValue
        else:
            return ""

    # the following code stolen from listen
    def get_val(self, node, name):
        """
            Node navigation
        """
        node = self.get_child(node, name)
        if node:
            return self.get_value(node[0])
        else:
            return ""
            
    def delete_podcast(self, widget, event):
        """ 
            Removes a podcast
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        path_id = tracks.get_column_id(self.db, 'paths', 'name', object.path)

        if not isinstance(object, PodcastWrapper): return
        dialog = gtk.MessageDialog(self.exaile.window,
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
            _("Are you sure you want to delete this podcast?"))
        if dialog.run() == gtk.RESPONSE_YES:
            self.db.execute("DELETE FROM podcasts WHERE path=?", (path_id,))
            self.db.execute("DELETE FROM podcast_items WHERE podcast_path=?", 
                (path_id,))

            self.model.remove(iter)
            self.tree.queue_draw()
            
        dialog.destroy()

    def add_url_to_station(self, item, event):
        """
            Adds a url to an existing station
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        station = model.get_value(iter, 1)
        
        dialog = xlmisc.MultiTextEntryDialog(self.exaile.window,
            _("Add Stream to Station"))
        dialog.add_field("URL:")
        dialog.add_field("Description:")
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_OK:
            (stream, desc) = dialog.get_values()

            self.db.execute("INSERT INTO radio_items(radio, url, "
                "title, description) VALUES( %s, %s, %s, %s)" % 
                common.tup(self.db.p, 4),
                (station, stream, desc, desc))
            
    def remove_station(self, item, event=None):
        """
            Removes a saved station
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        name = model.get_value(iter, 1)
        if not isinstance(name, CustomWrapper): return
        name = str(name)

        dialog = gtk.MessageDialog(self.exaile.window, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("Are you sure you want to permanently delete the selected"
            "station?"))
        result = dialog.run()
        dialog.destroy()
        radio_id = tracks.get_column_id(self.db, 'radio', 'name', name)

        if result == gtk.RESPONSE_YES:
            
            self.db.execute("DELETE FROM radio WHERE id=?", (radio_id,))
            self.db.execute("DELETE FROM radio_items WHERE radio=?", (radio_id,))
            if tracks.RADIO.has_key(name):
                del tracks.RADIO[name]

            self.model.remove(iter)
            self.tree.queue_draw()

    def open_station(self, playlist):
        """
            Opens a station
        """
        all = self.db.select("SELECT title, description, paths.name, bitrate FROM "
            "radio_items,radio,paths WHERE radio_items.radio=radio.id AND "
            "paths.id=radio_items.path AND radio.name=?", (playlist,))

        songs = xl.tracks.TrackData()
        tracks = trackslist.TracksListCtrl(self.exaile)
        self.exaile.playlists_nb.append_page(tracks,
            xlmisc.NotebookTab(self.exaile, playlist, tracks))
        self.exaile.playlists_nb.set_current_page(
            self.exaile.playlists_nb.get_n_pages() - 1)

        self.exaile.tracks = tracks

        for row in all:
            info = dict()
            info['artist'] = row[1]
            info['url'] = row[2]
            info['title'] = row[0]
            info['bitrate'] = row[3]

            track = media.RadioTrack(info)
            songs.append(track)
        tracks.set_songs(songs)
        tracks.queue_draw()

    def on_add_station(self, widget):
        """
            Adds a station
        """
        dialog = xlmisc.MultiTextEntryDialog(self.exaile.window, 
            _("Add Station"))
        dialog.add_field(_("Station Name:"))
        dialog.add_field(_("Description:"))
        dialog.add_field(_("URL:"))
        response = dialog.run()
        dialog.dialog.hide()

        if response == gtk.RESPONSE_OK:
            (name, desc, url) = dialog.get_values()
            if not name or not url:
                common.error(self.exaile.window, _("The 'Name' and 'URL'"
                    " fields are required"))
                self.on_add_station(widget)
                return

            c = self.db.record_count("radio", "radio=?", (name,))

            if c > 0:
                common.error(self.exaile.window, _("Station name already exists."))
                return
            radio_id = tracks.get_column_id(self.db, 'radio', 'name', name)
            path_id = tracks.get_column_id(self.db, 'paths', 'name', url)
            self.db.execute("INSERT INTO radio_items(radio, url, title, "
                "description) VALUES( ?, ?, ?, ? )", (radio_id, path_id, desc,
                desc))
            
            item = self.model.append(self.custom, [self.track, 
                CustomWrapper(name)])
            path = self.model.get_path(self.custom)
            self.tree.expand_row(path, False)


    def fetch_streams(self, rel=False):
        """
            Loads streams from a station.
            If the station hasn't been loaded or "rel" is True,
            it will be rescanned from
            shoutcase, otherwise it will be loaded from cache.
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()

        genre = self.model.get_value(iter, 1)

        tracks = trackslist.TracksListCtrl(self.exaile)
        self.exaile.playlists_nb.append_page(tracks,
            xlmisc.NotebookTab(self.exaile, genre, tracks))
        self.exaile.playlists_nb.set_current_page(
            self.exaile.playlists_nb.get_n_pages() - 1)
        self.exaile.tracks = tracks

        if rel or not tracks.load(genre):
            try:
                self.exaile.status.set_first("Loading streams from %s..." %
                    genre)
                shoutcast.ShoutcastThread(tracks, genre).start()
            except:
                xlmisc.log_exception()
                self.exaile.status.set_first("Error loading streams.", 2000)

    def on_add_to_station(self, widget, event):
        """
            Adds a playlist to the database
        """
        dialog = xlmisc.TextEntryDialog(self.exaile.window,
            _("Enter the name of the station"),
            _("Enter the name of the station"))
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if name == "": return
            c = self.db.record_count("radio", "name=?",
                (name,))

            if c > 0:
                common.error(self, _("Station already exists."))
                return

            station_id = tracks.get_column_id(self.db, 'radio', 
                'name', name)
            
            self.model.append(self.custom, [self.track, CustomWrapper(name)])
            self.tree.expand_row(self.model.get_path(self.custom), False)

            self.add_items_to_station(station=name)

    def add_items_to_station(self, item=None, event=None, 
        ts=None, station=None):
        """
            Adds the selected tracks tot he playlist
        """

        if ts == None: ts = self.exaile.tracks
        songs = ts.get_selected_tracks()

        if station:
            playlist = station
        else:
            playlist = item.get_child().get_text()

        station_id = tracks.get_column_id(self.db, 'radio', 'name', playlist)

        for track in songs:
            if not isinstance(track, media.StreamTrack): continue
            path_id = tracks.get_column_id(self.db, 'paths', 'name', track.loc)
            try:
                self.db.execute("INSERT INTO radio_items( radio, title, path, "
                    "description, bitrate ) " \
                    "VALUES( ?, ?, ?, ?, ? )",
                    (station_id, track.title, path_id,
                    track.artist, track.bitrate))
            except sqlite.IntegrityError:
                pass
        self.db.commit()

import locale
locale.setlocale(locale.LC_ALL, '')
class FilesPanel(object):
    """
        Represents a built in file browser.
    """

    def __init__(self, exaile):
        """
            Expects a Notebook and Exaile instance
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = exaile.xml
        self.first_dir = self.exaile.settings.get('files_panel_dir',
            os.getenv('HOME'))
        self.history = [self.first_dir]

        self.tree = xlmisc.DragTreeView(self, False)
        self.tree.set_headers_visible(True)
        container = self.xml.get_widget('files_box')
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(self.scroll, True, True)
        container.show_all()

        self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
        self.tree.set_model(self.model)
        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.directory = xlmisc.get_icon('gnome-fs-directory')
        self.track = gtk.gdk.pixbuf_new_from_file('images%strack.png' % os.sep)
        self.up = self.xml.get_widget('files_up_button')
        self.up.connect('clicked', self.go_up)
        self.back = self.xml.get_widget('files_back_button')
        self.back.connect('clicked', self.go_prev)
        self.next = self.xml.get_widget('files_next_button')
        self.next.connect('clicked', self.go_next)
        self.entry = self.xml.get_widget('files_entry')
        self.entry.connect('activate', 
            self.entry_activate)
        self.xml.get_widget('files_refresh_button').connect('clicked',
            self.refresh)
        self.counter = 0

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Path')
        col.pack_start(pb, False)
        col.pack_start(text, True)
        col.set_fixed_width(130)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_resizable(True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(text, text=1)
        self.i = 0

        self.tree.append_column(col)

        text = gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        col = gtk.TreeViewColumn('Size')
        col.set_fixed_width(50)
        col.set_resizable(True)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.pack_start(text, False)
        col.set_attributes(text, text=2)
        self.tree.append_column(col)

        self.load_directory(self.first_dir, False)
        self.tree.connect('row-activated', self.row_activated)
        self.menu = xlmisc.Menu()
        self.menu.append(_("Append to Playlist"), self.append)

    def drag_get_data(self, treeview, context, sel, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        uris = []
        for path in paths:
            iter = self.model.get_iter(path)
            value = self.model.get_value(iter, 1)
            value = "%s%s%s" % (self.current, os.sep, value)
            uris.append(urllib.quote(value))

        sel.set_uris(uris)

    def button_press(self, widget, event):
        """
            Called to show the menu when someone right clicks
        """
        selection = self.tree.get_selection()
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        if selection.count_selected_rows() <= 1: return False

    def append(self, widget, event):
        """
            Appends recursively the selected directory/files
        """
        self.exaile.status.set_first(_("Scanning and adding files..."))
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        songs = tracks.TrackData()

        for path in paths:
            iter = self.model.get_iter(path)
            value = model.get_value(iter, 1)
            value = "%s%s%s" % (self.current, os.sep, value)
            (stuff, ext) = os.path.splitext(value)
            if os.path.isdir(value):
                self.append_recursive(songs, value)
            elif ext in media.SUPPORTED_MEDIA:
                tr = tracks.read_track(self.exaile.db,
                    self.exaile.all_songs,
                    value, adddb=False)
                if tr:
                    songs.append(tr)

        if songs:
            self.exaile.append_songs(songs, title=_("Playlist"))
        self.counter = 0
        self.exaile.status.set_first(None)

    def append_recursive(self, songs, dir):
        """
            Appends recursively
        """
        for root, dirs, files in os.walk(dir):
            for f in files:
                (stuff, ext) = os.path.splitext(f)
                if ext in media.SUPPORTED_MEDIA:
                    tr = tracks.read_track(self.exaile.db,
                        self.exaile.all_songs,
                        os.path.join(root, f), adddb=False)
                    if tr:
                        songs.append(tr)
                if self.counter >= 15:
                    xlmisc.finish()
                    self.counter = 0
                else:
                    self.counter += 1

    def refresh(self, widget):
        """
            Refreshes the current view
        """
        self.load_directory(self.current, False)

    def entry_activate(self, widget, event=None):
        """
            Called when the user presses enter in the entry box
        """
        dir = self.entry.get_text()
        if not os.path.isdir(dir):
            self.entry.set_text(self.current)
            return
        self.load_directory(dir)

    def go_next(self, widget):
        """
            Goes to the next entry in history
        """
        self.i += 1 
        self.load_directory(self.history[self.i], False)
        if self.i >= len(self.history) - 1:
            self.next.set_sensitive(False)
        if len(self.history):
            self.back.set_sensitive(True)
            
    def go_prev(self, widget):
        """
            Previous entry
        """
        self.i -= 1
        self.load_directory(self.history[self.i], False)
        if self.i == 0:
            self.back.set_sensitive(False)
        if len(self.history):
            self.next.set_sensitive(True)

    def go_up(self, widget):
        """
            Moves up one directory
        """
        cur = re.sub('(.*)%s[^%s]*$' % (os.sep, os.sep),
            r'\1', self.current)
        if not cur: cur = os.sep

        self.load_directory(cur)

    def row_activated(self, *i):
        """
            Called when someone double clicks a row
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()

        for path in paths:
            iter = self.model.get_iter(path)
            value = model.get_value(iter, 1)
            dir = "%s%s%s" % (self.current, os.sep, value)
            if os.path.isdir(dir):
                self.load_directory(dir)
            else:
                if dir.endswith('.pls') or dir.endswith('.m3u'):
                    self.exaile.import_m3u(dir, True)
                else:
                    tr = tracks.read_track(self.exaile.db, self.exaile.all_songs,
                        dir, adddb=False)
                    if tr:
                        self.exaile.append_songs((tr, ), title=_('Playlist'))

    def load_directory(self, dir, history=True):
        """
            Loads a directory into the files view
        """
        self.exaile.settings['files_panel_dir'] = dir
        self.current = dir
        directories = []
        files = []
        for path in os.listdir(dir):
            if path.startswith('.'): continue
            full = "%s%s%s" % (dir, os.sep, path)
            if os.path.isdir(full):
                directories.append(path)

            else:
                (stuff, ext) = os.path.splitext(path)
                if ext in media.SUPPORTED_MEDIA:
                    files.append(path)

        directories.sort()
        files.sort()

        self.model.clear()
        
        for d in directories:
            self.model.append([self.directory, d, '-'])

        for f in files:
            info = os.stat("%s%s%s" % (dir, os.sep, f))
            size = info[6]
            size = size / 1024
            size = locale.format("%d", size, True) + " KB"

            self.model.append([self.track, f, size])

        self.tree.set_model(self.model)
        self.entry.set_text(self.current)
        if history: 
            self.back.set_sensitive(True)
            self.history = self.history[:self.i + 1]
            self.history.append(self.current)
            self.i = len(self.history) - 1
            self.next.set_sensitive(False)
