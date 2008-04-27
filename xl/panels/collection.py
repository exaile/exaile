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

import gtk, os, gobject, urllib
from gettext import gettext as _, ngettext
from xl import common, media, library, xlmisc
from xl.gui import editor, playlist
import xl.path

class CollectionPanel(object):
    """
        Represents the entire collection in a tree
    """
    rating_images = []
    rating_width = 64   # some default value
    old_r_w = -1
    name = 'col'
    def __init__(self, exaile):
        """
            Initializes the collection panel. Expects a parent and exaile
            object
        """

        # FIXME: Refactor get_selected_items to be get_selected_tracks
        self.get_selected_tracks = self.get_selected_items

        self.xml = exaile.xml
        self.exaile = exaile
        self.db = exaile.db

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object, str)
        self.model_blank = gtk.TreeStore(gtk.gdk.Pixbuf, object, str)
        self.scan_label = None
        self.queue_item = -1
        self.scan_progress = None
        self.showing = False
        self.tree = None
        self.keyword = None
        self.track_cache = dict()
        self.start_count = 0
        self.artist_image = gtk.gdk.pixbuf_new_from_file(xl.path.get_data(
            'images', 'artist.png'))
        self.year_image = gtk.gdk.pixbuf_new_from_file(xl.path.get_data(
            'images', 'year.png'))
        self.album_image = self.exaile.window.render_icon('gtk-cdrom',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.track_image = gtk.gdk.pixbuf_new_from_file(xl.path.get_data(
            'images', 'track.png'))
        self.genre_image = gtk.gdk.pixbuf_new_from_file(xl.path.get_data(
            'images', 'genre.png'))
        self.iplaylist_image = gtk.gdk.pixbuf_new_from_file(xl.path.get_data(
            'images', 'playlist.png'))
        self.connect_id = None
        self.setup_widgets()
        playlist.create_rating_images(self)
        self.cover_cache = {}

    def setup_widgets(self):
        """
            Sets up the widgets for this panel
        """
        self.box = self.xml.get_widget('%s_box' % self.name)
        self.choice = self.xml.get_widget('%s_combo_box' % self.name)

        active = self.exaile.settings.get_int('ui/%s_active_view' % self.name, 0)
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
                # TRANSLATORS: Scanning filesystem for tracks
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
        if library.PopulateThread.running:
            library.PopulateThread.stopped = True

    def on_search(self, widget=None, event=None):
        """
            Searches tracks and reloads the tree.  A timer is started
            in LoadTree if keyword is not None which will expand the items
            of the tree until the matched node is found
        """
        self.keyword = unicode(self.filter.get_text(), 'utf-8')
        self.start_count += 1
        self.load_tree()

    def create_popup(self):
        """
            Creates the popup menu for this tree
        """
        menu = xlmisc.Menu()
        # TRANSLATORS: Append selected track(s) to current playlist
        self.append = menu.append(_("Append to Current"),
            self.append_to_playlist, 'gtk-add')

        pm = xlmisc.Menu()
        self.new_playlist = pm.append(_("New Playlist"),
            self.add_items_to_playlist, 'gtk-new')
        pm.append_separator()

        rows = self.db.select("SELECT name FROM playlists WHERE type=0 ORDER BY"
            " name")

        for row in rows:
            pm.append(row[0], self.add_to_playlist)

        menu.append_menu(_("Add to Playlist"), pm, 'gtk-add')

        pixbuf = xlmisc.get_text_icon(self.exaile.window, u'\u2610', 16, 16)
        icon_set = gtk.IconSet(pixbuf)
        
        factory = gtk.IconFactory()
        factory.add_default()        
        factory.add('exaile-queue-icon', icon_set)

        self.queue_item = menu.append(_("Queue Items"),
            self.append_to_playlist, 'exaile-queue-icon')
        menu.append_separator()
        # TRANSLATORS: Put selected track(s) on the blacklist
        self.blacklist = menu.append(_("Blacklist Selected"),
            self.remove_items, 'gtk-delete')
        # TRANSLATORS: Remove selected track(s) from the disk
        self.remove = menu.append(_("Delete Selected"), 
            self.remove_items, 'gtk-delete')

        n_selected = len(self.get_selected_tracks())
        menu.append_separator()
        em = xlmisc.Menu()

        em.append(_("Edit Information"), lambda e, f:
            editor.TrackEditor(self.exaile, self), 'gtk-edit')
        em.append_separator()

        rm = xlmisc.Menu()

        for i in range(0, 5):
            if i == 0:
                item = rm.append('-', lambda w, e, i=i:
                    editor.update_rating(self, i))
            else:
                item = rm.append_image(self.rating_images[i],
                    lambda w, e, i=i: editor.update_rating(self, i))

        em.append_menu(_("Rating"), rm)
        menu.append_menu(ngettext("Edit Track", "Edit Tracks", n_selected), em,
            'gtk-edit')

        self.menu = menu

    def add_to_playlist(self, widget, event):
        """
            Adds items to the playlist
        """
        playlist = widget.get_child().get_label()
        items = self.get_selected_items()
        self.exaile.playlists_panel.add_items_to_playlist(playlist, items)

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        urls = self.get_urls_for(self.get_selected_items())
        selection.set_uris(urls)

    def get_urls_for(self, items): # may be overridden
        """
            Returns the the items' URLs
        """
        return [urllib.quote(item.loc.encode(xlmisc.get_default_encoding()))
            for item in items]

    def append_recursive(self, iter, add):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)        
        while True:
            field = self.model.get_value(iter, 2)
            if self.model.iter_has_child(iter):
                self.append_recursive(iter, add)
            elif field == 'title':
                track = self.model.get_value(iter, 1)
                if not track.loc in add:
                    add.append(track.loc)
            
            iter = self.model.iter_next(iter)
            if not iter: break

    def get_selected_items(self):
        """
            Finds all the selected tracks
        """

        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        found = [] 
        for path in paths:
            iter = self.model.get_iter(path)
            field = self.model.get_value(iter, 2)
            if self.model.iter_has_child(iter):
                self.append_recursive(iter, found)
            else:
                track = self.model.get_value(iter, 1)
                if field == 'title':
                    if not track.loc in found:
                        found.append(track.loc)

        add = library.TrackData()
        for row in found:
            add.append(self.all.for_path(row))

        return add

    def remove_items(self, item, event):
        """
            Removes or blacklists tracks
        """

        add = self.get_selected_items() 
        device_delete = []

        if item == self.remove:
            result = common.yes_no_dialog(self.exaile.window,
                _("Are you sure you want to permanently remove the " \
                "selected tracks from disk?"))

            if result != gtk.RESPONSE_YES: return

            for track in add:
                if track.type == 'device':
                    device_delete.append(track)
                    continue
                else:
                    for track in add:
                        os.remove(track.loc)
                path_id = library.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                self.db.execute("DELETE FROM tracks WHERE path=?", (path_id,))
                self.db.execute("DELETE FROM playlist_items WHERE path=?",(path_id,))

        if item == self.blacklist:
            result = common.yes_no_dialog(self.exaile.window,
                _("Are you sure you want to blacklist the selected tracks?"))
            if result != gtk.RESPONSE_YES: 
                return
            for track in add:
                if track.type == 'device':
                    continue
                path_id = library.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                self.db.execute("UPDATE tracks SET blacklisted=1 WHERE path=?", (path_id,))
            
        for track in add:
            try: self.exaile.all_songs.remove(track)
            except: pass
            try: self.exaile.songs.remove(track)
            except: pass
            try: self.exaile.playlist_songs.remove(track)
            except: pass

        if device_delete:   
            self.remove_tracks(device_delete)

        if self.exaile.tracks: 
            self.exaile.tracks.set_songs(self.exaile.songs)
        self.track_cache = dict()
        self.load_tree()

    def add_items_to_playlist(self, item=None, *e):

        add = self.get_selected_items()
        self.exaile.playlists_panel.on_add_playlist(item, None, add)

    def append_to_playlist(self, item=None, event=None):
        add = self.get_selected_items()
        queue = (item == self.queue_item)

        self.exaile.playlist_manager.append_songs(add, queue, True)

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
                field = self.model.get_value(iter, 2)

                # if this is a device panel, check to see if the current
                # driver wants to handle this object, and if so, return
                if self.name == 'device':
                    if self.driver and hasattr(self.driver, 'check_open_item'):
                        if self.driver.check_open_item(object):
                            return False
                if field == 'album':
                    self.append_to_playlist()
                    return False

            for path in paths:
                iter = self.model.get_iter(path)
                object = self.model.get_value(iter, 1)
                if self.model.iter_has_child(iter):
                    self.tree.expand_row(path, False)
                else:
                    self.append_to_playlist() 
            return False

        iter = self.model.get_iter(path[0])
        object = self.model.get_value(iter, 1)

        self.create_popup()

        if self.name == 'device':
            self.show_device_panel_menu(widget, event, object)
            return True

        self.menu.popup(None, None, None, event.button, event.time)
        if selection.count_selected_rows() <= 1: return False
        return True

    def track_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if object is None: return
        field = model.get_value(iter, 2)

        if field == 'nofield':
            cell.set_property('text', object)
            return
        if hasattr(object, field):
            info = getattr(object, field)
            if not info: info = _('Unknown')
            cell.set_property('text', info)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        pass

    def get_initial_root(self, model):
        """
            gets the initial root node
        """
        return None

    def load_tree(self, event=None):
        """
            Builds the tree.  If self.keyword is not None, it will start a timer
            that will expand each node until a node that matches the keyword
            is found
        """
        self.current_start_count = self.start_count
        if not self.tree:
            self.tree = xlmisc.DragTreeView(self)
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

            self.tree.set_row_separator_func(
                lambda m, i: m.get_value(i, 1) is None)

        # clear out the tracks if this is a first time load or the refresh
        # button is pressed
        if event: 
            xlmisc.log("Clearing tracks cache")
            self.track_cache = dict()

        self.model.clear()
        self.tree.set_model(self.model_blank)
        self.root = self.get_initial_root(self.model)
    
        self.image_map = {
            "album": self.album_image,
            "artist": self.artist_image,
            "genre": self.genre_image,
            "title": self.track_image,
            "year": self.year_image,
        }

        if self.keyword == "": self.keyword = None

        orders = (
            ('artist', 'album', 'track', 'title'),
            ('album', 'track', 'title'),
            ('genre', 'artist', 'album', 'track', 'title'),
            ('genre', 'album', 'artist', 'track', 'title'),
            ('year', 'artist', 'album', 'track', 'title'),
            ('year', 'album', 'artist', 'track', 'title'),
            ('artist', 'year', 'album', 'track', 'title')
        )
        self.order = orders[self.choice.get_active()]

        o_map = {
            'album': 'LSTRIP_SPEC(albums.name), disc_id', 
            'artist': 'LSTRIP_SPEC(THE_CUTTER(artists.name))',
            'genre': 'LSTRIP_SPEC(genre)',
            'title': 'LSTRIP_SPEC(title)',
            'track': 'track', 
            'year' : 'LSTRIP_SPEC(year)',
        }
        order_by = ', '.join((o_map[o] for o in self.order))

        self.where = """
            SELECT 
                paths.name 
            FROM tracks, albums, paths, artists
            WHERE 
                blacklisted=0 AND
                (
                    paths.id=tracks.path AND
                    albums.id=tracks.album AND
                    artists.id=tracks.artist 
                )
            ORDER BY 
                %s
            """ % order_by


        # save the active view setting
        self.exaile.settings['ui/%s_active_view' % self.name] = self.choice.get_active()

        # if this is a collection panel, don't alter self.all, as this messes
        # up inheriting from it
        if self.name == 'col':
            all = self.exaile.all_songs
            self.all = all
        else:
            # FIXME: This is evil OOP; it should use method overriding instead,
            # e.g. see drag_get_data and get_urls_for.
            if isinstance(self, device.DevicePanel):
                self.all = None

        songs = None
        key = "%s %s" % (self.where, self.keyword)
        try:
            songs = self.track_cache[key]
        except:
            pass

        if not songs or self.name== 'device':
            songs = self.search_tracks(self.keyword, self.all)
            self.track_cache[key] = songs

        if self.current_start_count != self.start_count: return

        self.append_info(self.root, songs)

        if self.connect_id: gobject.source_remove(self.connect_id)
        self.connect_id = None
        self.filter.set_sensitive(True)

    def search_tracks(self, keyword, all):
        """
            Searches for songs
        """
        return library.search_tracks(self.exaile.window, self.db, all,
            self.keyword, None, self.where)

    def __check_track_function(self, model, path, iter, track_needed):
        """
           Checks if track is equal to given while traversing the tree,
           called by show_in_collection
        """
        node = self.model.get_value(iter, 1)
        if isinstance(node, media.Track) and node.loc == track_needed.loc:
            self.__track_path = path
            return True

    def show_in_collection(self, track):
        """
           Shows given track in collection panel:
           1. Expand tree to this node
           2. Scroll tree to centerize node vertically if possible
           3. Set cursor to it
        """
        self.__track_path = None
        self.model.foreach(self.__check_track_function, track)
        path = self.__track_path
        if path is None:
            common.info(self.exaile.window,
                _("Track is not present in collection"))
        else:
            self.tree.set_model(self.model)
            self.tree.expand_to_path(path)
            gobject.idle_add(self.tree.scroll_to_cell, path, None, True, 0.5)
            gobject.idle_add(self.tree.set_cursor, path)

    @common.threaded
    def append_info(self, node, songs=None, unknown=False):
        """
            Appends all related info and organizes the tree based on self.order
            Only the very last item of self.order will be a child node
        """

        show_covers = self.exaile.settings.get_boolean('ui/covers_in_collection', False)
        order_nodes = common.idict()
        order = []
        last_songs = []
        for field in self.order:
            if field == "track": continue
            order.append(field)

        for field in order:
            order_nodes[field] = common.idict()

        expanded_paths = []
        last_char = None
        use_alphabet = self.exaile.settings.get_boolean("ui/use_alphabet", True)
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

                # print separators
                if first and info and use_alphabet:
                    temp = library.the_cutter(library.lstrip_special(info).upper()).upper()

                    if not temp:
                        first_char = ' '
                    else:
                        first_char = temp[0]
                    if not last_char: # First row, don't add separator.
                        last_char = first_char
                    if first_char != last_char:
                        if not first_char.isalpha():
                            first_char = '0-9'
                        if first_char != last_char:
                            last_char = first_char
                            self.model.append(parent, [None, None, None]) # separator

                if not info: 
                    if not unknown and first:
                        last_songs.append(track)
                        break
                    info = _("Unknown")
                first = False

                if field == "title":
                    n = self.model.append(parent, [self.track_image,
                        track, field])
                else:
                    string = "%s - %s" % (string, info)
                    if not string in node_for:
                        if field == "album" and show_covers:                                            
                            album_cover = self.exaile.cover_manager.fetch_cover(track, True)
                            if not album_cover in self.cover_cache:
                                self.cover_cache[album_cover] = \
                                gtk.gdk.pixbuf_new_from_file_at_size(album_cover, 20, 20)
                            parent = self.model.append(parent, 
                                [self.cover_cache[album_cover], track, field])
                        else:                            
                            parent = self.model.append(parent, 
                                [self.image_map[field], track, field])

                        if info == "track": info = track
                        node_for[string] = parent
                    else: parent = node_for[string]

                if self.keyword and last_parent:
                    if self.keyword.lower() in common.to_unicode(info).lower():
                        expanded_paths.append(self.model.get_path(
                            last_parent))
                last_parent = parent

        # make sure "Unknown" items end up at the end of the list
        if not unknown and last_songs:
            if use_alphabet:
                self.model.append(node, [None, None, None]) # separator
            self.append_info(self.root, last_songs, True)

        gobject.idle_add(self.tree.set_model, self.model)
        for path in expanded_paths:
            gobject.idle_add(self.tree.expand_to_path, path)

        if self.root:
            path = self.model.get_path(self.root)
            gobject.idle_add(self.tree.expand_row, path, False)
            if self.name == 'device':
                gobject.idle_add(self.done_loading_tree)

# HACK: Work around failing recursive import.
# See fixme in load_tree for why this is needed and how it should be fixed.
import device
