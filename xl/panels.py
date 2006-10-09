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
import common, trackslist, shoutcast, scrobbler
import media, time, thread, re, copy, threading
import urllib
from xml.dom import minidom
from pysqlite2.dbapi2 import OperationalError
from pysqlite2 import dbapi2 as sqlite
from gettext import gettext as _
import pygtk
pygtk.require('2.0')
import gtk, gobject
random.seed()

try:
    import gpod
    IPOD_AVAILABLE = True
except:
    IPOD_AVAILABLE = False

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
        self.filter = self.xml.get_widget('%s_search' % self.name)
        self.filter.connect('activate', self.on_search)
        self.filter.connect('key-release-event',
            self.__key_release)
        self.key_id = None
        self.search_button = self.xml.get_widget('%s_search_button' %
            self.name)
        self.search_button.connect('clicked', self.on_search)
        self.create_popup()

    def __key_release(self, *e):
        """
            Called when someone releases a key.
            Sets up a timer to simulate live-search
        """
        if self.key_id:
            gobject.source_remove(self.key_id)
            self.key_id = None

        self.key_id = gobject.timeout_add(150, self.on_search)

    def update_progress(self, percent):
        """
            Updates scanning progress meter
        """
        if percent <= -1:
            self.scan_label.hide()
            self.progress.hide()
            self.showing = False
            self.exaile.status.set_first(_("Finished scanning collection."),
                2000)

        else:
            self.showing = True
            if not self.scan_label:
                self.progress = gtk.ProgressBar()
                self.box.pack_end(self.progress, False, False)
                self.scan_label = gtk.Label(_("Scanning..."))
                self.scan_label.set_alignment(0, 0)
                self.box.pack_end(self.scan_label, False, False)

            self.scan_label.show()
            self.progress.show()
            self.progress.set_fraction(percent)

    def on_search(self, widget=None, event=None):
        """
            Searches tracks and reloads the tree.  A timer is started
            in LoadTree if keyword is not None which will expand the items
            of the tree until the matched node is found
        """
        self.keyword = self.filter.get_text()

        if isinstance(self, iPodPanel):
            self.load_tree(None, False)
        else:
            self.load_tree()

    def __run_expand(self):
        """
            Expands items in the tree to the node that matches the keyword
        """
        xlmisc.log("Exanding")

        iter = self.model.get_iter_first()
        if not iter: return
        while True:
            self.__expand_items(iter, self.keyword.lower())
            iter = self.model.iter_next(iter)
            if not iter: break

    def __expand_items(self, parent, keyword):
        """
            Expands items in the tree to the node that matches the keyword
        """
        iter = self.model.iter_children(parent)
        if not iter: return
        while True:
            if self.model.iter_has_child(iter):
                self.__expand_items(iter, keyword)

            track = self.model.get(iter, 1)[0]

            if isinstance(track, media.Track):
                items = ('title', 'album', 'artist')
                for item in items:
                    val = str(getattr(track, item))
                    if val.lower().find(keyword.lower()) > -1:
                        self.__expand_to_top(parent)
                        break
            else:
                if isinstance(track, AlbumWrapper):
                    track = track.name
                if not isinstance(track, iPodPlaylist) and \
                    track.lower().find(keyword.lower()) > -1:
                    self.__expand_to_top(parent)
            iter = self.model.iter_next(iter)
            if not iter: break

    def __expand_to_top(self, iter):
        """
            Expands rows
        """
        parent = self.model.iter_parent(iter)
        if parent:
            path = self.model.get_path(parent)
            self.tree.expand_row(path, False)

        path = self.model.get_path(iter)
        self.tree.expand_row(path, False)

    def create_popup(self):
        """
            Creates the popup menu for this tree
        """
        menu = xlmisc.Menu()
        self.append = menu.append(_("Append to Current"),
            self.__append_items)

        pm = xlmisc.Menu()
        self.new_playlist = pm.append(_("Add to Playlist"),
            self.__append_items)
        pm.append_separator()

        rows = self.db.select("SELECT playlist_name FROM playlists ORDER BY"
            " playlist_name")

        for row in rows:
            pm.append(row[0], self.__add_to_playlist)

        menu.append_menu(_("Add to Playlist"), pm)
        self.queue_item = menu.append(_("Queue Items"), self.__append_items)
        menu.append_separator()
        self.blacklist = menu.append(_("Blacklist Selected"),
            self.__append_items)
        self.remove = menu.append(_("Delete Selected"), 
            self.__append_items)
        self.menu = menu

    def __add_to_playlist(self, widget, event):
        """
            Adds items to the playlist
        """
        playlist = widget.get_child().get_label()
        items = self.__append_items(None, None, True)
        self.exaile.playlists_panel.add_items_to_playlist(playlist, items)

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        loc = self.__append_items(None, None, True)

        if isinstance(self, iPodPanel):
            loc = ["ipod://%s" % urllib.quote(l.loc) for l in loc]
        else:
            loc = [urllib.quote(str(l.loc)) for l in loc]

        selection.set_uris(loc)

    def __append_recursive(self, iter, add, queue=False):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)        
        while True:
            if self.model.iter_has_child(iter):
                self.__append_recursive(iter, add, queue)
            else:
                track = self.model.get_value(iter, 1)
                add.append(track.loc)
            
            iter = self.model.iter_next(iter)
            if not iter: break

    def __append_items(self, item=None, event=None, return_only=False):
        """
            Adds items to the songs list based on what is selected in the tree
            The songs are then added to a playlist, queued, removed, or 
            blacklisted, depending on which menu item was clicked
        """
        queue = False
        if item == self.queue_item: queue = True
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        add = [] 
        for path in paths:
            iter = self.model.get_iter(path)
            if self.model.iter_has_child(iter):
                self.__append_recursive(iter, add, queue)
            else:
                track = self.model.get_value(iter, 1)
                add.append(track.loc)

        # create an sql query based on all of the paths that were found.
        # this way we can order them by track number to make sure they
        # are added to the playlist as they are sorted in the album
        add = ["path=\"%s\"" % x.replace('"', r'\"') for x in add]
        where = " OR ".join(add)
        cur = self.db.cursor()
        add = tracks.TrackData()
        rows = self.db.select("SELECT path FROM tracks WHERE %s ORDER BY artist, " \
            "album, track, title" % where)

        for row in rows:
            add.append(self.all.for_path(row[0]))

        if return_only: return add

        if item == self.remove:
            result = common.yes_no_dialog(self.exaile.window,
                _("Are you sure you want to permanently remove the " \
                "selected tracks from disk?"))

            if result != gtk.RESPONSE_YES: return
            for track in add:
                os.remove(track.loc)

            self.db.execute("DELETE FROM tracks WHERE %s" % where)
            self.db.execute("DELETE FROM playlist_items WHERE %s" % where)

        if item == self.blacklist:
            result = common.yes_no_dialog(self.exaile.window,
                _("Are you sure you want to blacklist the selected tracks?"))
            if result != gtk.RESPONSE_YES: return
            self.db.execute("UPDATE tracks SET blacklisted=1 WHERE %s" % where)
            
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
            self.load_tree()
            return

        if item == self.new_playlist:
            self.exaile.playlists_panel.on_add_playlist(item, None, add)
            return

        self.exaile.append_songs(add, queue, True)

    def button_pressed(self, widget, event):
        """
            Called when someone clicks on the tree
        """
        selection = self.tree.get_selection()
        (x, y) = event.get_coords()
        x = int(x)
        y = int(y)
        path = self.tree.get_path_at_pos(x, y)
        if not path: return True

        if event.type == gtk.gdk._2BUTTON_PRESS:
            (model, paths) = selection.get_selected_rows()

            # check to see if it's a double click on an album
            if len(paths) == 1:
                iter = self.model.get_iter(path[0])
                object = self.model.get_value(iter, 1)
                if isinstance(object, AlbumWrapper):
                    self.__append_items()
                    return

            for path in paths:
                iter = self.model.get_iter(path)
                object = self.model.get_value(iter, 1)
                if self.model.iter_has_child(iter):
                    self.tree.expand_row(path, False)
                elif isinstance(object, iPodPlaylist):
                    self.open_playlist()
                else:
                    self.__append_items() 
            return False

        if event.button != 3: 
            if selection.count_selected_rows() <= 1: return False
            else: 
                if selection.path_is_selected(path[0]): 
                    if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        selection.unselect_path(path[0])
                        return True
                    else:
                        return False
                elif not event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    return False
                return False       

        else:
            iter = self.model.get_iter(path[0])
            object = self.model.get_value(iter, 1)
            if isinstance(object, iPodPlaylist):
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

    def load_tree(self, event=None):
        """
            Builds the tree.  If self.keyword is not None, it will start a timer
            that will expand each node until a node that matches the keyword
            is found
        """
        if not self.tree:
            self.tree = self.xml.get_widget('%s_tree' % self.name)
            self.tree.connect('button_press_event',
                self.button_pressed)
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
            self.targets = [('text/uri-list', 0, 0)]
            self.tree.connect('drag_data_get', self.drag_get_data)
            self.tree.connect('drag_begin', self.__drag_begin)
            self.tree.connect('drag_end', self.__drag_end)
            self.tree.connect('drag_motion', self.__drag_motion)
            self.tree.drag_source_set(gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY)
            self.tree.drag_source_set_icon_stock('gtk-dnd')

            if isinstance(self, iPodPanel):
                self.tree.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
                    gtk.gdk.ACTION_COPY)
                self.tree.connect('drag-data-received', 
                    self.drag_data_received)

        # clear out the tracks if this is a first time load or the refresh
        # button is pressed
        if event: 
            print "Clearing tracks cache"
            self.tracks_cache = dict()

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)

        self.tree.set_model(self.model)
        self.root = None
    
        if isinstance(self, iPodPanel) and self.lists:
            root_playlist = self.lists[0]
            other = self.lists[1:]

            self.iroot = self.model.append(self.root, [self.ipod_image, root_playlist])

            for playlist in other:
                item = self.model.append(self.iroot, [self.iplaylist_image, playlist])

            self.root = self.model.append(self.root, [self.ipod_image, _("iPod Collection")])
            self.tree.expand_row(self.model.get_path(self.iroot), False)

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
            where = "SELECT path FROM tracks WHERE blacklisted=0 ORDER BY " \
                "genre, track, title COLLATE NOCASE"

        if self.choice.get_active() == 0:
            self.order = ('artist', 'album', 'track', 'title')
            where = "SELECT path, %s FROM tracks WHERE " \
                "blacklisted=0 ORDER BY %s COLLATE NOCASE" % \
                (", ".join(self.order), ", ".join(self.order))

        if self.choice.get_active() == 1:
            self.order = ('album', 'track', 'title')
            where = "SELECT path, album, track, title FROM tracks " \
                "WHERE blacklisted=0 ORDER BY " \
                "album, track, artist, title COLLATE NOCASE"

        # save the active view setting
        self.exaile.settings['active_view'] = self.choice.get_active()

        all = self.exaile.all_songs

        if self.ipod: all = self.all
        else: self.all = all

        if self.track_cache.has_key("%s %s" % (where, self.keyword)) \
            and self.track_cache["%s %s" % (where, self.keyword)] and \
            not self.ipod:
            songs = self.track_cache["%s %s" % (where, self.keyword)]
        else:
            songs = xl.tracks.search_tracks(self.exaile, self.db,
                all, self.keyword, None, where)
        self.track_cache["%s %s" % (where, self.keyword)] = songs

        self.__append_info(self.root, songs)
        if isinstance(self, iPodPanel) and self.root:
            self.tree.expand_row(self.model.get_path(self.root), False)

        if self.connect_id: gobject.source_remove(self.connect_id)
        self.connect_id = None
        if self.keyword != None: 
            self.connect_id = gobject.timeout_add(150, self.__run_expand)

    def __drag_end(self, list, context):
        """
            Called when the dnd is ended
        """
        self.__dragging = False
        self.tree.unset_rows_drag_dest()
        self.tree.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, gtk.gdk.ACTION_COPY)

    def __drag_begin(self, list, context):
        """
            Called when dnd is started
        """
        self.__dragging = True

        context.drag_abort(gtk.get_current_event_time())
        selection = self.tree.get_selection()
        if selection.count_selected_rows() > 1:
            self.tree.drag_source_set_icon_stock('gtk-dnd-multiple')
        else: self.tree.drag_source_set_icon_stock('gtk-dnd')
        return False

    def __drag_motion(self, treeview, context, x, y, timestamp):
        """
            Called when a row is dragged over this treeview
        """
        if not isinstance(self, iPodPanel): return
        self.tree.enable_model_drag_dest(self.targets,
            gtk.gdk.ACTION_DEFAULT)
        info = treeview.get_dest_row_at_pos(x, y)
        if not info: return
        treeview.set_drag_dest_row(info[0], info[1])

    def __append_info(self, node, songs=None, unknown=False):
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

        for track in songs:
            parent = node
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

        # make sure "Unknown" items end up at the end of the list
        if not unknown and last_songs:
            self.__append_info(self.root, last_songs, True)

class iPodPlaylist(object):
    """
        Container for iPod playlist
    """
    def __init__(self, playlist):
        """
            requires an gpod playlist object
        """
        self.playlist = playlist
        self.name = playlist.name

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

            gpod.itdb_cp_track_to_ipod(track, str(song.loc), None)
            gpod.itdb_track_add(self.itdb, track, -1)
            mpl = gpod.itdb_playlist_mpl(self.itdb)
            gpod.itdb_playlist_add_track(mpl, track, -1)
            if song.ipod_playlist:
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

        self.all = xl.tracks.TrackData()
        self.ipod = True
        self.connected = False
        if not IPOD_AVAILABLE: return

        self.transfer_queue = None
        self.all = []
        self.transferring = False
        self.write_lock = threading.Lock()
        self.queue = None

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            When tracks are dragged to this list
        """
        self.tree.unset_rows_drag_dest()
        self.tree.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, gtk.gdk.ACTION_COPY)
        if not self.connected:
            common.error(self.exaile.window, _("Not connected to iPod"))
            return
        path = self.tree.get_path_at_pos(x, y)

        if path:
            iter = self.model.get_iter(path[0])
            object = self.model.get_value(iter, 1)
        if isinstance(object, iPodPlaylist) and path:
            playlist = object
            print "Playlist %s" % playlist.name
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
            else:
                song = self.exaile.all_songs.for_path(url)
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
            self.box = self.xml.get_widget('ipod_box')
            self.queue = iPodTransferQueue(self)
            self.box.pack_start(self.queue, False, False)

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

    def create_ipod_menu(self):
        """
            Creates the ipod menu
        """
        self.ipod_menu = xlmisc.Menu()
        self.open = self.ipod_menu.append(_("Open Playlist"),
            self.open_playlist)
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

    def create_popup(self):
        """
            Creates the popup menu"
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
                playlist.playlist.name = name
                playlist.name = name
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

    def delete_tracks(self, tracks):
        """
            Deletes tracks from the iPod
        """
        if not self.connected or not self.itdb: return

        for track in tracks:
            track = track.ipod_track()
            file = gpod.itdb_filename_on_ipod(track)
            if file != None:
                os.unlink(file)
            for playlist in gpod.sw_get_playlists(self.itdb):
                if gpod.itdb_playlist_contains_track(playlist, track):
                    gpod.itdb_playlist_remove_track(playlist, track)
            gpod.itdb_track_unlink(track)
        self.save_database()            

    def __append_covers_recursive(self, iter, add):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)

        while True:
            object = self.model.get_value(iter, 1)
            if self.model.iter_has_child(iter):
                self.__append_covers_recursive(iter, add)
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
                self.__append_covers_recursive(iter, add)
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
        tracks = xl.tracks.search_tracks(self.exaile, self.db, self.all, None,
            str(playlist))

        self.exaile.new_page(playlist.name, tracks)
        self.exaile.tracks.playlist = playlist

    def get_cover_location(self, track):
        """
            Gets the location of the album art
        """
        db = self.exaile.db
        row = db.read_one("albums", "image", 
            "artist=? AND album=? AND image!=''",
            (track.artist, track.album))
        if not row or row[0] == '': return None
        return "%s%scovers%s%s" % (self.exaile.get_settings_dir(), os.sep,
            os.sep, str(row[0]))

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
        self.lists = []

        for line in file("sql/db.sql"):
            line = line.strip()
            self.db.execute(line, [], True)
        self.db.check_version("sql", echo=False)
        self.db.commit()

        if not self.itdb: 
            connected = False
            self.all = []
            self.list_dict = dict()
            return False
        if not os.path.isdir(self.exaile_dir):
            os.mkdir(self.exaile_dir)
        self.all = xl.tracks.TrackData()

        for playlist in gpod.sw_get_playlists(self.itdb):
            if playlist.type == 1:
                self.lists.insert(0, iPodPlaylist(playlist))
            else:
                self.lists.append(iPodPlaylist(playlist))
            self.db.execute("INSERT INTO playlists(playlist_name) VALUES(?)",
                (playlist.name,), True)
            for track in gpod.sw_get_playlist_tracks(playlist):
                loc = self.mount + track.ipod_path.replace(":", "/")
                self.db.execute("REPLACE INTO playlist_items(playlist, "
                    "path) VALUES( ?, ? )", (playlist.name, loc), True)

        for track in gpod.sw_get_tracks(self.itdb):
            loc = self.mount + track.ipod_path.replace(":", "/")
            try:
                loc = unicode(loc)

                # check for "the" tracks
                artist = track.artist
                the_track = ""
                if artist and artist.lower()[:4] == "the ":
                    the_track = artist[:4]
                    artist = artist[4:]
                self.db.execute("REPLACE INTO tracks( path, " \
                    "title, artist, album, track, length," \
                    "bitrate, genre, year, user_rating, the_track ) " \
                    "VALUES( ?, ?, ?, ?, ?, ?, ?, " \
                    "?, ?, ?, ? )",

                    (loc,
                    unicode(track.title),
                    unicode(artist),
                    unicode(track.album),
                    unicode(track.track_nr),
                    unicode(track.tracklen / 1000),
                    unicode(track.bitrate),
                    unicode(track.genre),
                    unicode(track.year),
                    unicode(track.rating),
                    the_track), True)

                itrack = track
                track = xl.tracks.read_track(self.db, None, loc, True, True)
                if not track: continue
                track.itrack = itrack
                
                self.all.append(track)

            except UnicodeDecodeError:
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
        handle = open(self.log_file, "w")
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

        thread.start_new_thread(scrobbler.submit, (submit,))
        self.update_log()
        xlmisc.log("All tracks have been submitted from iPod, log has been updated.")


    def load_tree(self, event=None, connect=True):
        """
            Loads the tree (and connects to the ipod if refresh was pressed)
        """

        if connect: self.connect_ipod()
        xlmisc.log("Loading iPod collection tree")
        CollectionPanel.load_tree(self, event)

class PlaylistsPanel(object):
    """ 
        The playlists panel 
    """
    SMART_PLAYLISTS = ("Entire Library", "Highest Rated", "Top 100", "Most Played",
        "Least Played", "Random 100", "Rating > 5", "Rating > 3")

    def __init__(self, exaile):
        """
            Creates the playlist panel
        """
        self.exaile = exaile
        self.db = self.exaile.db
        self.xml = exaile.xml

        self.custom = xlmisc.ListBox(self.xml.get_widget('custom_playlists'))
        targets = [('text/uri-list', 0, 0)]
        self.smart = xlmisc.ListBox(self.xml.get_widget('smart_playlists'), 
            self.SMART_PLAYLISTS)
        self.custom.list.enable_model_drag_dest(targets,
            gtk.gdk.ACTION_DEFAULT)
        self.custom.list.connect('drag_data_received', self.drag_data_received)

        self.smart.list.connect('row-activated', self.load_smart)
        self.custom.list.connect('row-activated', self.__open_playlist)
        self.xml.get_widget('playlists_add_button').connect('clicked', 
            self.on_add_playlist)
        self.xml.get_widget('playlists_remove_button').connect('clicked',
            self.__remove_playlist)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags tracks to the smart playlists panel
        """
        error = ""
        path = self.custom.list.get_path_at_pos(x, y)
        if not path: playlist = self.on_add_playlist(None)
        else:
            iter = self.custom.store.get_iter(path[0])
            if not iter:
                playlist = self.on_add_playlist(None) 
                if not playlist: return True
            else:
                playlist = self.custom.store.get_value(iter, 0)

        if not playlist: return True
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

        if error:
            common.scrolledMessageDialog(self.exaile.window,
                error, _("The following errors did occur"))

        self.add_items_to_playlist(playlist, songs)

    def __remove_playlist(self, widget):
        """
            Asks if the user really wants to delete the selected playlist, and
            then does so if they choose 'Yes'
        """

        playlist = self.custom.get_selection()
        if not playlist: return
        dialog = gtk.MessageDialog(self.exaile.window, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("Are you sure you want to permanently delete the selected"
            " playlist?"))
        if dialog.run() == gtk.RESPONSE_YES:
            if not playlist: return
            self.db.execute("DELETE FROM playlists WHERE playlist_name=?",
                (playlist,))
            self.db.execute("DELETE FROM playlist_items WHERE playlist=?",
                (playlist,))
            self.db.commit()
            
            self.custom.remove(playlist)
        dialog.destroy()

    def load_smart(self, widget=None, path=None, column=None):
        """
            Loads a smart playlist
        """
        smart = self.smart.get_selection()

        w = None
        if smart == "Top 100":
            w = "SELECT path FROM tracks ORDER BY rating " \
                "DESC LIMIT 100"
        elif smart == "Highest Rated":
            w = "SELECT path FROM tracks ORDER BY user_rating DESC " \
                "LIMIT 100"
        elif smart == "Most Played":
            w = "SELECT path FROM tracks ORDER " \
                "BY plays DESC LIMIT 100"
        elif smart == "Least Played":
            w = "SELECT path FROM tracks ORDER " \
                "BY plays ASC LIMIT 100"
        elif smart == "Rating > 5":
            w = "SELECT path FROM tracks WHERE user_rating > 5 " \
                "ORDER BY artist, album, track"
        elif smart == "Rating > 3":
            w = "SELECT path FROM tracks WHERE user_rating > 3 " \
                "ORDER BY artist, album, track"
        elif smart == "Random 100":
            w = "SELECT path FROM tracks"
            songs = tracks.TrackData()
            for song in self.exaile.all_songs:
                songs.append(song)

            random.shuffle(songs)
            songs = songs[0:100]

        if smart != "Random 100":
            songs = xl.tracks.search_tracks(self, self.db,
                self.exaile.all_songs, None, None, w)

        self.exaile.new_page(self.smart.get_selection(), songs)

    def __open_playlist(self, widget, tracks, tra):
        """
            Opens a playlist
        """
        playlist = self.custom.get_selection()

        xlmisc.log("Loading playlist %s" % playlist)
        self.playlist_songs = xl.tracks.search_tracks(self, self.db,
            self.exaile.all_songs, None, playlist)
        self.exaile.new_page(playlist, self.playlist_songs)
        self.exaile.on_search()
        self.exaile.tracks.playlist = playlist

    def load_playlists(self):
        """
            Loads all playlists and adds them to the list
        """
        rows = self.db.select("SELECT playlist_name FROM playlists " \
            "ORDER BY playlist_name")

        playlists = []
        for row in rows:
            playlists.append(row[0])

        self.custom.set_rows(playlists)

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
            c = self.db.record_count("playlists", "playlist_name=?",
                (name,))

            if c > 0:
                common.error(self.exaile.window, _("Playlist already exists."))
                return name

            self.db.execute("INSERT INTO playlists(playlist_name) VALUES(?)",
                (name,))
            self.db.commit()
                
            self.custom.append(name)

            if type(widget) == gtk.MenuItem:
                self.add_items_to_playlist(name, items)
            return name
        else: return None

    def add_items_to_playlist(self, playlist, tracks=None):
        """
            Adds the selected tracks tot he playlist
        """
        if type(playlist) == gtk.MenuItem:
            playlist = playlist.get_child().get_label()

        if tracks == None: tracks = self.exaile.tracks.get_selected_tracks()

        for track in tracks:
            if isinstance(track, media.StreamTrack): continue
            self.db.execute("REPLACE INTO playlist_items( playlist, path ) " \
                "VALUES( ?, ? )", (playlist, track.loc))
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

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.tree.set_model(self.model)

        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.folder = xlmisc.get_icon('gnome-fs-directory')

        self.track = gtk.gdk.pixbuf_new_from_file('images%strack.png' %
            os.sep)
        self.custom = self.model.append(None, [self.open_folder, "Saved Stations"])
        self.podcast = self.model.append(None, [self.open_folder, "Podcasts"])

        # load all saved stations from the database
        rows = self.db.select("SELECT radio_name FROM radio "
            "ORDER BY radio_name")
        for row in rows:
            self.model.append(self.custom, [self.track, CustomWrapper(row[0])])

        # load podcasts
        rows = self.db.select("SELECT title, path FROM podcasts")
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
        self.tree.connect('row-expanded', self.__on_expanded)
        self.tree.connect('row-collapsed', self.__on_collapsed)
        self.tree.connect('button-press-event', self.button_pressed)
        self.xml.get_widget('radio_add_button').connect('clicked',
            self.on_add_station)
        self.xml.get_widget('radio_remove_button').connect('clicked',
            self.__remove_station)
        self.setup_menus()

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
                self.__open_station(object.name)
            elif isinstance(object, PodcastWrapper):
                self.__open_podcast(object)
            else:
                self.__fetch_streams()

    def __open_podcast(self, wrapper):
        """
            Opens a podcast
        """
        row = self.db.read_one("podcasts", "description", "path=?",
            (wrapper.path, ))
        if not row: return

        desc = row[0]
        rows = self.db.select("SELECT path, title, description, length, "
            "pub_date FROM podcast_items WHERE podcast_path=?", 
            (wrapper.path,))

        songs = tracks.TrackData()
        for row in rows:
            t = common.strdate_to_time(row[4])
            year = time.strftime("%x", time.localtime(t))
            info = ({
                'title': row[1],
                'artist': row[2],
                'album': desc,
                'url': row[0],
                'year': year, 
                'podcast_duration': row[3]
            })
            song = media.PodcastTrack(info)
            songs.append(song)

        self.exaile.new_page(wrapper.name, songs)

    def cell_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, CustomWrapper):
            cell.set_property('text', str(object))
        else:
            cell.set_property('text', str(object))
            
    def __on_collapsed(self, tree, iter, path):
        """
            Called when someone collapses a tree item
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.model.set_value(iter, 0, self.folder)
        self.tree.queue_draw()

    def __on_expanded(self, tree, iter, path):
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
            self.__fetch_streams(True))

        # custom playlist menu
        self.cmenu = xlmisc.Menu()
        self.add = self.cmenu.append(_("Add Stream to Station"), 
            self.__add_url_to_station)
        self.delete = self.cmenu.append(_("Delete this Station"),
            self.__remove_station)

        self.podmenu = xlmisc.Menu()
        self.podmenu.append(_("Add Feed"), self.__on_add_podcast)
        self.podmenu.append(_("Refresh Feed"), self.__refresh_feed)
        self.podmenu.append(_("Delete Feed"), self.__delete_podcast)

    def __refresh_feed(self, widget, event):
        """
            Refreshes a feed
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        if isinstance(object, PodcastWrapper):
            self.__refresh_podcast(object.path, iter)

    def __on_add_podcast(self, widget, event):
        """
            Called when a request to add a podcast is made
        """
        dialog = xlmisc.TextEntryDialog(self.exaile.window, _("Enter the location of"
            " the podcast"), _("Add a podcast"))

        if dialog.run() == gtk.RESPONSE_OK:
            name = dialog.get_value()
            dialog.destroy()
            if self.db.record_count("podcasts", "path=?", 
                (name, )):
                common.error(self.exaile.window, 
                    _("A podcast with that url already"
                    " exists"))
                return

            self.db.execute("INSERT INTO podcasts( path ) VALUES( ? )", (name,))

            item = self.model.append(self.podcast,
                [self.track, PodcastWrapper("Fetching...", name)])
            self.tree.expand_row(self.model.get_path(self.podcast), False)

            self.__refresh_podcast(name, item)
        dialog.destroy()

    def __refresh_podcast(self, path, item):
        """
            Refreshes a podcast
        """
        thread = xlmisc.ThreadRunner(self.__fetch_podcast_xml)
        thread.path = path
        thread.item = item
        thread.start()

    def __fetch_podcast_xml(self, thread):
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

        gobject.idle_add(self.__parse_podcast_xml, path, item, xml)

    def __parse_podcast_xml(self, path, iter, xml):
        """
            Parses the xml from the podcast and stores the information to the
            database
        """
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
        self.db.execute("DELETE FROM podcast_items WHERE podcast_path=?",
            (path,))
        self.db.execute("UPDATE podcasts SET title=?, "
            "pub_date=?, description=?, image=? WHERE"
            " path=?", (title, pub_date,
            description, image, path))

        self.model.set_value(iter, 1, PodcastWrapper(title, path))
        items = root.getElementsByTagName('item')
        for item in items:
            title = self.get_val(item, 'title')
            link = self.get_val(item, 'link')
            desc = self.get_val(item, 'description')
            enc = self.get_child(item, 'enclosure')
            date = self.get_val(item, 'pubDate')
            if enc:
                size = enc[0].getAttribute('length')
                length = enc[0].getAttribute('duration')
                loc = enc[0].getAttribute("url")

            self.db.execute("INSERT INTO podcast_items( podcast_path, "
                "path, pub_date, description, size, title, length ) VALUES( "
                "?, ?, ?, ?, ?, ?, ? )", 
                (path, loc, date, desc, size, title, length)) 

        self.db.db.commit()
        gobject.timeout_add(500, self.__open_podcast, PodcastWrapper(description, path))

    def get_child(self, node, name):
        """ 
            Gets a child node
        """
        return node.getElementsByTagName(name)

    def __get_value(self, node):
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
            return self.__get_value(node[0])
        else:
            return ""
            
    def __delete_podcast(self, widget, event):
        """ 
            Removes a podcast
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)

        if not isinstance(object, PodcastWrapper): return
        dialog = gtk.MessageDialog(self.exaile.window,
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
            _("Are you sure you want to delete this podcast?"))
        if dialog.run() == gtk.RESPONSE_YES:
            self.db.execute("DELETE FROM podcasts WHERE path=?",
                (object.path,))
            self.db.execute("DELETE FROM podcast_items WHERE podcast_path=?",
                (object.path,))

            self.model.remove(iter)
            self.tree.queue_draw()
            
        dialog.destroy()

    def __add_url_to_station(self, item, event):
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

            self.db.execute("REPLACE INTO radio_items(radio, url, "
                "title, description) VALUES( ?, ?, ?, ?)",
                (station, stream, desc, desc))
            
    def __remove_station(self, item, event=None):
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

        if result == gtk.RESPONSE_YES:
            self.db.execute("DELETE FROM radio WHERE radio_name=?",
                (name,))
            self.db.execute("DELETE FROM radio_items WHERE radio=?",
                (name,))

            self.model.remove(iter)
            self.tree.queue_draw()

    def __open_station(self, playlist):
        """
            Opens a station
        """
        all = self.db.select("SELECT title, description, url, bitrate FROM "
            "radio_items WHERE radio=?", (playlist,))

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

            c = self.db.record_count("radio", "radio_name=?",
                (name,))

            if c > 0:
                common.error(self.exaile.window, _("Station name already exists."))
                return

            self.db.execute("INSERT INTO radio(radio_name) VALUES(?)",
                (name,))
            self.db.execute("INSERT INTO radio_items(radio, url, title, "
                "description) VALUES("
                "?, ?, ?, ?)", (name, url, desc, desc))
            
            item = self.model.append(self.custom, [self.track, 
                CustomWrapper(name)])
            path = self.model.get_path(self.custom)
            self.tree.expand_row(path, False)


    def __fetch_streams(self, rel=False):
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
            c = self.db.record_count("radio", "radio_name=?",
                (name,))

            if c > 0:
                common.error(self, _("Station already exists."))
                return

            self.db.execute("INSERT INTO radio(radio_name) VALUES(?)",
                (name,))
            self.db.commit()
            
            self.model.append(self.custom, [self.track, CustomWrapper(name)])
            self.tree.expand_row(self.model.get_path(self.custom), False)

            self.add_items_to_station(station=name)

    def add_items_to_station(self, item=None, event=None, 
        tracks=None, station=None):
        """
            Adds the selected tracks tot he playlist
        """

        if tracks == None: tracks = self.exaile.tracks
        tracks = tracks.get_selected_tracks()

        if station:
            playlist = station
        else:
            playlist = item.get_child().get_text()

        for track in tracks:
            if not isinstance(track, media.StreamTrack): continue
            self.db.execute("REPLACE INTO radio_items( radio, title, url, "
                "description, bitrate ) " \
                "VALUES( ?, ?, ?, ?, ? )",
                (playlist, track.title, track.loc,
                track.artist, track.bitrate))
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
        self.history = [os.getenv('HOME')]

        self.tree = self.xml.get_widget('files_tree')
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

        self.load_directory(os.getenv('HOME'), False)
        self.tree.connect('row-activated', self.row_activated)
        self.tree.connect('button-press-event', self.button_press)
        targets = [('text/uri-list', 0, 0)]
        self.tree.connect('drag_data_get', self.drag_get_data)
        self.tree.drag_source_set(gtk.gdk.BUTTON1_MASK, targets,
            gtk.gdk.ACTION_COPY)
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
        (x, y) = event.get_coords()
        x = int(x)
        y = int(y)
        path = self.tree.get_path_at_pos(x, y)
        if not path: return True
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)

        if selection.count_selected_rows() <= 1: return False
        else: 
            if selection.path_is_selected(path[0]): 
                if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    selection.unselect_path(path[0])
                    return True
                else:
                    return False
            elif not event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                return False
            return False       

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
                self.__append_recursive(songs, value)
            elif ext in media.SUPPORTED_MEDIA:
                tr = tracks.read_track(self.exaile.db,
                    self.exaile.all_songs,
                    value)
                if tr:
                    songs.append(tr)

        if songs:
            self.exaile.append_songs(songs, title=_("Playlist"))
        self.counter = 0
        self.exaile.status.set_first(None)

    def __append_recursive(self, songs, dir):
        """
            Appends recursively
        """
        for root, dirs, files in os.walk(dir):
            for f in files:
                (stuff, ext) = os.path.splitext(f)
                if ext in media.SUPPORTED_MEDIA:
                    tr = tracks.read_track(self.exaile.db,
                        self.exaile.all_songs,
                        os.path.join(root, f))
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
                        dir)
                    if tr:
                        self.exaile.append_songs((tr, ), title=_('Playlist'))

    def load_directory(self, dir, history=True):
        """
            Loads a directory into the files view
        """
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
