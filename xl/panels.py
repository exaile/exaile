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

import xl.tracks, os, sys, md5, random, db, track, tracks, xlmisc
import common, trackslist, filtergui
import media, time, thread, re, copy, threading
import urllib
from xl import media
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

def day_calc(x, inc, field, symbol='>='):
    values = {
        'seconds': 1,
        'minutes': 60,
        'hours': 60 * 60,
        'days': 60 * 60 * 24,
        'weeks': 60 * 60 * 24 * 7
    }

    seconds = int(x) * values[inc]
    t = time.time() - seconds
    t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))
    return "%s %s '%s'" % (field, symbol, t)

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

class EntryDaysField(MultiEntryField):
    def __init__(self, result_generator):
        MultiEntryField.__init__(self, result_generator, n=1,
            labels=(None, _('days')),
            widths=(50,))

DATE_FIELDS = (_('seconds'), _('minutes'), _('hours'), _('days'), _('weeks'))
class SpinDateField(filtergui.SpinButtonAndComboField):
    def __init__(self, result_generator):
        filtergui.SpinButtonAndComboField.__init__(self, 
            result_generator, DATE_FIELDS)

class SpinSecondsField(filtergui.SpinLabelField):
    def __init__(self, result_generator):
        filtergui.SpinLabelField.__init__(self, result_generator, 
            _('seconds'))

class SpinRating(filtergui.SpinLabelField):
    def __init__(self, result_generator):
        filtergui.SpinLabelField.__init__(self, result_generator, '',
            8)

class SpinNothing(filtergui.SpinLabelField):
    def __init__(self, result_generator):
        filtergui.SpinLabelField.__init__(self, result_generator, '')

CRITERIA = [
    (N_('Artist'), [
        (N_('is'), (EntryField, lambda x:
            'artists.name = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'artists.name != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'artists.name LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'artists.name NOT LIKE "%%%s%%"' % x)),
        ]),
    (N_('Album'), [
        (N_('is'), (EntryField, lambda x:
            'albums.name = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'albums.name != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'albums.name LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'albums.name NOT LIKE "%%%s%%"' % x)),
        ]),
    (N_('Genre'), [
        (N_('is'), (EntryField, lambda x:
            'genre = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'genre != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'genre LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'genre NOT LIKE "%%%s%%"' %x)),
        ]),
    (N_('User Rating'), [
        (N_('at least'), (SpinRating, lambda x:
            'user_rating >= %s' % x)),
        (N_('at most'), (SpinRating, lambda x:
            'user_rating <= %s' % x))]),
    (N_('System Rating'), [
        (N_('at least'), (SpinRating, lambda x:
            'rating >= %s' % x)),
        (N_('at most'), (SpinRating, lambda x:
            'rating <= %s' % x))
        ]),
    (N_('Number of Plays'), [
        (N_('at least'), (SpinNothing, lambda x:
            'plays >= %s' % x)),
        (N_('at most'), (SpinNothing, lambda x:
            'plays <= %s' %x))
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
        (N_('at least'), (SpinSecondsField, lambda x:
            'length >= %s' % x)),
        (N_('at most'), (SpinSecondsField, lambda x:
            'length <= %s' % x)),
        ]),
    (N_('Date Added'), [
        (N_('in the last'), (SpinDateField, 
            lambda x, i: day_calc(x, i, 'time_added'))),
        (N_('not in the last'), (SpinDateField, 
            lambda x, i: day_calc(x, i, 'time_added', '<'))),
        ]),
    (N_('Last Played'), [
        (N_('in the last'), (SpinDateField, 
            lambda x: day_calc(x, 'last_played'))),
        (N_('not in the last'), (SpinDateField, 
            lambda x: day_calc(x, 'last_played', '<'))),
        ]),
    (N_('Location'), [
        (N_('is'), (EntryField, lambda x:
            'paths.name = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'paths.name != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'paths.name LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'paths.name NOT LIKE "%%%s%%"' % x)),
        ])
    ]

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

        # FIXME: Refactor get_selected_items to be get_selected_tracks
        self.get_selected_tracks = self.get_selected_items

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
        self.artist_image = gtk.gdk.pixbuf_new_from_file('images%sartist.png' %
            os.sep)
        self.album_image = self.exaile.window.render_icon('gtk-cdrom', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.track_image = gtk.gdk.pixbuf_new_from_file('images%strack.png' % 
            os.sep)
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
        self.load_tree()

    def create_popup(self):
        """
            Creates the popup menu for this tree
        """
        menu = xlmisc.Menu()
        self.append = menu.append(_("Append to Current"),
            self.append_to_playlist)

        pm = xlmisc.Menu()
        self.new_playlist = pm.append(_("New Playlist"),
            self.add_items_to_playlist, 'gtk-new')
        pm.append_separator()

        rows = self.db.select("SELECT name FROM playlists WHERE type=0 ORDER BY"
            " name")

        for row in rows:
            pm.append(row[0], self.add_to_playlist)

        menu.append_menu(_("Add to Playlist"), pm)
        self.queue_item = menu.append(_("Queue Items"),
            self.append_to_playlist)
        menu.append_separator()
        self.blacklist = menu.append(_("Blacklist Selected"),
            self.remove_items)
        self.remove = menu.append(_("Delete Selected"), 
            self.remove_items)

        menu.append_separator()
        menu.append(_("Edit Information"), lambda e, f:
            track.TrackEditor(self.exaile, self), 'gtk-edit')

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
        loc = self.get_selected_items()

        if isinstance(self, DevicePanel):
            driver_name = self.get_driver_name()
            loc = ["device_%s://%s" % (driver_name, 
                urllib.quote(l.loc)) for l in loc]
        else:
            loc = [urllib.quote(l.loc.encode(xlmisc.get_default_encoding())) for l in loc]
        
        selection.set_uris(loc)

    def append_recursive(self, iter, add):
        """
            Appends items recursively to the added songs list.  If this
            is a genre, artist, or album, it will search into each one and
            all of the tracks contained
        """
        iter = self.model.iter_children(iter)        
        while True:
            if self.model.iter_has_child(iter):
                self.append_recursive(iter, add)
            else:
                track = self.model.get_value(iter, 1)
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
            if self.model.iter_has_child(iter):
                self.append_recursive(iter, found)
            else:
                track = self.model.get_value(iter, 1)
                found.append(track.loc)

        add = tracks.TrackData()
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
                os.remove(track.loc)

            for track in add:
                if track.type == 'device':
                    device_delete.append(track)
                    continue
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
                if track.type == 'device':
                    continue
                path_id = tracks.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                self.db.execute("UPDATE tracks SET blacklisted=1 WHERE ?", (path_id,))
            
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

                # if this is a device panel, check to see if the current
                # driver wants to handle this object, and if so, return
                if self.name == 'device':
                    if self.driver and hasattr(self.driver, 'check_open_item'):
                        if self.driver.check_open_item(object):
                            return False
                if isinstance(object, AlbumWrapper):
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
            return

        self.menu.popup(None, None, None, event.button, event.time)
        if selection.count_selected_rows() <= 1: return False
        return True

    def track_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, media.Track):
            cell.set_property('text', str(object.title))
        else:
            cell.set_property('text', str(object))

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

        # clear out the tracks if this is a first time load or the refresh
        # button is pressed
        if event: 
            print "Clearing tracks cache"
            self.track_cache = dict()

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.model_blank = gtk.TreeStore(gtk.gdk.Pixbuf, object)

        self.tree.set_model(self.model_blank)
        self.root = self.get_initial_root(self.model)
    
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
            self.where = """
                SELECT 
                    paths.name, 
                    artists.name, 
                    track, 
                    title 
                FROM tracks, paths, artists, albums 
                WHERE 
                    blacklisted=0 AND 
                    (
                        paths.id=tracks.path AND 
                        artists.id=tracks.artist AND 
                        albums.id=tracks.album
                    ) 
                ORDER BY 
                    LOWER(genre), 
                    THE_CUTTER(artists.name),
                    LOWER(albums.name),
                    disc_id,
                    track, 
                    title
            """

        if self.choice.get_active() == 0:
            self.order = ('artist', 'album', 'track', 'title')
            self.where = """
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
                    disc_id,
                    track, 
                    title
            """

        if self.choice.get_active() == 1:
            self.order = ('album', 'track', 'title')
            self.where = """
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
                    disc_id,
                    track, 
                    THE_CUTTER(artists.name), 
                    title
            """

        # save the active view setting
        self.exaile.settings['ui/%s_active_view' % self.name] = self.choice.get_active()

        # if this is a collection panel, don't alter self.all, as this messes
        # up inheriting from it
        if self.name == 'col':
            all = self.exaile.all_songs
            self.all = all
        else:
            if isinstance(self, DevicePanel):
                self.all = None

        songs = None
        key = "%s %s" % (self.where, self.keyword)
        try:
            songs = self.track_cache[key]
        except:
            pass
        if not songs:
            songs = self.search_tracks(self.keyword, self.all)
            self.track_cache[key] = songs

        if self.current_start_count != self.start_count: return

        self.append_info(self.root, songs)

        if self.connect_id: gobject.source_remove(self.connect_id)
        self.connect_id = None
        self.filter.set_sensitive(True)
        if self.root:
            path = self.model.get_path(self.root)
            if path: gobject.timeout_add(500, self.tree.expand_row, path,
                False)

    def search_tracks(self, keyword, all):
        """
            Searches for songs
        """
        return xl.tracks.search_tracks(self.exaile.window, self.db, all,
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
           common.info(self.exaile.window, _("Track is not present in collection"))
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

class EmptyDriver(object):
    def __init__(self):
        self.all = tracks.TrackData()

    def search_tracks(self, *e):
        return self.all

    def disconnect(self):
        pass

    def connect(self, *e):
        pass

class DeviceTransferQueue(gtk.VBox):
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
        self.transferring = False
        self.stopped = True

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

        self.stop = gtk.Button()
        image = gtk.Image()
        image.set_from_stock('gtk-stop', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.stop.set_image(image)
        self.stop.connect('clicked', self.on_stop)

        self.transfer = gtk.Button(_("Transfer"))
        buttons.pack_end(self.transfer, False, False)
        buttons.pack_end(self.clear, False, False)
        buttons.pack_end(self.stop, False, False)
        self.clear.connect('clicked',
            self.on_clear)
        self.transfer.connect('clicked', self.start_transfer)

        self.pack_start(buttons, False, False)
        targets = [('text/uri-list', 0, 0)]
        self.list.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, targets,
            gtk.gdk.ACTION_COPY)
        self.list.list.connect('drag_data_received', self.drag_data_received)

    def check_transfer(self):
        """
            Checks to see if a transfer is in progress, and if so, it throws
            an error
        """
        if self.transferring:
            common.error(self.panel.exaile.window, _('A transfer is in '
                'progress, please wait for it to stop before attempting '
                'to perform this operation.'))
            return False

        return True

    def on_stop(self, *e):
        """
            Stops the transfer
        """
        self.transferring = False
        self.stopped = True

    def on_clear(self, widget):
        """
            Clears the queue
        """
        if not self.check_transfer(): return
        self.panel.queue = None
        self.hide()
        self.destroy()

    @common.threaded
    def start_transfer(self, widget):
        """
            Runs the transfer
        """
        if self.transferring: return
        self.transferring = True
        self.stopped = False
        gobject.idle_add(self.panel.exaile.status.set_first, "Starting "
            "transfer...", 3000)
        items = self.list.rows[:]
        total = len(self.list.rows)
        self.panel.transferring = True
        driver = self.panel.driver
        count = 0
        while True:
            if self.stopped: return
            if not items: break
            item = items.pop()
            driver.put_item(item)
            per = float(count) / float(total)
            count += 1
            gobject.idle_add(self.update_progress, item, per)
            print "set percent to %s" % per

        if self.stopped: return
        gobject.idle_add(self.progress.set_fraction, 1)
        gobject.idle_add(self.panel.exaile.status.set_first, "Finishing"
            " transfer...", 3000)
        gobject.idle_add(self.panel.transfer_done)
        self.transferring = False

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
        if not self.check_transfer(): return
        self.panel.drag_data_received(tv, context, x, y, selection, info,
            etime)

class DeviceDragItem(object):
    def __init__(self, track, target):
        self.track = track
        self.target = target

    def __str__(self):
        return str(self.track)

class DevicePanel(CollectionPanel):
    """
        Collection panel that allows for different collection drivers
    """
    name = 'device'
    def __init__(self, exaile):
        CollectionPanel.__init__(self, exaile)
        self.driver = None
        self.drivers = {}
        self.all = tracks.TrackData()
        self.tree = xlmisc.DragTreeView(self, True, True)
        self.tree.set_headers_visible(False)

        self.chooser = self.xml.get_widget('device_driver_chooser')
        self.track_count = self.xml.get_widget('device_track_count')
        self.connect_button = self.xml.get_widget('device_connect_button')
        self.connect_button.connect('clicked', self.change_driver)

        self.store = gtk.ListStore(str, object)
        cell = gtk.CellRendererText()
        self.chooser.pack_start(cell)
        self.chooser.add_attribute(cell, 'text', 0)
        self.chooser.set_model(self.store)

        container = self.xml.get_widget('%s_box' % self.name)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(scroll, True, True)
        container.reorder_child(scroll, 3)
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
        self.update_drivers(True)
        self.transferring = False
        self.connected = False
        self.queue = None
        self.chooser.set_active(0)

    def show_device_panel_menu(self, widget, event, item):
        """
            Shows the device panel menu
        """
        if self.driver and hasattr(self.driver, 'get_menu'):
            menu = self.driver.get_menu(item, self.menu)

        menu.popup(None, None, None, event.button, event.time)

    def remove_tracks(self, tracks):
        """ 
            Removes tracks from the current device
        """
        if not hasattr(self.driver, 'remove_tracks'):
            common.error(self.exaile.window, _("This device does "
                "not support removing tracks"))
            return

        self.driver.remove_tracks(tracks)

    def get_initial_root(self, model):
        if self.driver is not None and hasattr(self.driver, 
            'get_initial_root'):
            return getattr(self.driver, 'get_initial_root')(model)
        else:
            return None

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        self.tree.unset_rows_drag_dest()
        self.tree.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.tree.targets, 
            gtk.gdk.ACTION_COPY)
        if not self.connected:
            common.error(self.exaile.window, _("Not connected to any media"
                " device"))
            return
        path = self.tree.get_path_at_pos(x, y)

        target = None
        if path:
            iter = self.model.get_iter(path[0])
            target = self.model.get_value(iter, 1)

        loc = selection.get_uris()
        items = []
        for url in loc:
            url = urllib.unquote(url)
            m = re.search(r'^device_(\w+)://', url)
            if m:
                song = self.get_song(url)
            else:
                song = self.exaile.all_songs.for_path(url)

            if song:
                items.append(DeviceDragItem(song, target))

        if items:
            self.add_to_transfer_queue(items)

    def add_to_transfer_queue(self, items):
        """
            Adds to the device transfer queue
        """
        if not hasattr(self.driver, 'put_item'):
            common.error(self.exaile.window, _("The current device "
                " does not support transferring music."))
            return
        if self.transferring:
            common.error(self.exaile.window, _("There is a transfer "
                "currently in progress.  Please wait for it to "
                "finish"))
            return

        if not self.queue:
            self.queue_box = self.xml.get_widget('device_queue_box')
            self.queue = DeviceTransferQueue(self)
            self.queue_box.pack_start(self.queue, False, False)

        queue = self.queue.songs
        queue.extend(items)

        self.queue.list.set_rows(queue)
        if queue:
            self.queue.show_all()
        else:
            self.queue.hide()
            self.queue.destroy()
            self.queue = None

    def transfer_done(self):
        """
            called when the transfer is complete
        """
        if hasattr(self.driver, 'transfer_done'):
            self.driver.transfer_done()
        if self.queue:
            self.queue.hide()
            self.queue.destroy()
            self.queue = None
        self.transferring = None
        self.load_tree()

    def change_driver(self, button):
        """
            Changes the current driver
        """
        if self.driver and self.queue:
            if not self.queue.check_transfer():
                return
        if self.connected:
            self.driver.disconnect()
            self.driver = EmptyDriver()
            self.connected = False
            img = gtk.Image()
            img.set_from_stock('gtk-disconnect', gtk.ICON_SIZE_BUTTON)
            self.track_count.set_label("0 tracks")
            self.load_tree(True)
            self.connect_button.set_image(img)
            return

        iter = self.chooser.get_active_iter()
        driver = self.store.get_value(iter, 1)
        if not isinstance(driver, EmptyDriver):
            self.connect(driver)
            img = gtk.Image()
            img.set_from_stock('gtk-connect', 
                gtk.ICON_SIZE_BUTTON)
            self.connect_button.set_image(img)

    def update_drivers(self, initial=False):
        """
            Updates the driver list
        """
        if not initial:
            self.exaile.show_device_panel(len(self.drivers) > 0)
        count = 1
        select = 0
        self.store.clear()
        self.store.append(['None', EmptyDriver()])

        for k, v in self.drivers.iteritems():
            if k == self.driver:
                select = count

            self.store.append([v, k])            

        if select > 0:
            self.chooser.disconnect(self.change_id)
            self.chooser.set_active(select)
            self.change_id = self.chooser.connect('changed', self.change_driver)
        else:
            self.chooser.set_active(0)

    def add_driver(self, driver, name):
        if not self.drivers.has_key(driver):
            self.drivers[driver] = name
        self.update_drivers()

    def remove_driver(self, driver):
        if self.drivers.has_key(driver):
            del self.drivers[driver]
        self.update_drivers()

    def connect(self, driver):
        self.track_count.set_label("Connecting...")
        try:
            driver.connect(self)
        except:
            common.error(self.exaile.window, _("Error connecting to device"))
            xlmisc.log_exception()
            self.on_connect_complete(None)

    def on_error(self, error):
        """
            Called when there is an error in a device driver during connect
        """
        common.error(self.exaile.window, error)
        self.on_connect_complete(None)
        
    def on_connect_complete(self, driver):
        """ 
            Called when the connection is complete
        """
        self.driver = driver
        if not self.driver:
            self.driver = EmptyDriver()
            self.connected = False
            img = gtk.Image()
            img.set_from_stock('gtk-disconnect', gtk.ICON_SIZE_BUTTON)
            self.connect_button.set_image(img)
        else:
            self.connected = True
        self.track_count.set_label("%d tracks" % len(self.driver.all))

        self.load_tree()

    def search_tracks(self, keyword, all=None):
        if not self.driver: self.all = tracks.TrackData()
        else: self.all = self.driver.search_tracks(keyword)
        return self.all

    def get_driver_name(self):
        if not self.driver: return None
        return self.driver.name

    def get_song(self, loc):
        return self.all.for_path(loc.replace('device_%s://' % self.driver.name, ''))

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
        self.setDaemon(True)
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
            temp = tracks.read_track(None, None, download_path)

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

class LastFMWrapper(object):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class EmptyRadioDriver(object):
    """
        Empty Driver
    """
    def __init__(self):
        pass

class PRadioGenre(object):
    def __init__(self, name, driver=None, extra=None):
        self.name = name
        self.extra = extra
        self.driver = driver

    def __str__(self):
        return self.name

class PRadioDriver(object):
    pass

class PRadioPanel(object):
    """
        This will be a pluggable radio panel.  Plugins like shoutcast and
        live365 will go here
    """
    name = 'pradio'
    def __init__(self, exaile):
        """
            Initializes the panel
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = exaile.xml
        self.tree = self.xml.get_widget('radio_service_tree')
        icon = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn('radio')
        col.pack_start(icon)
        col.pack_start(text)
        col.set_attributes(icon, pixbuf=0)
        col.set_cell_data_func(text, self.cell_data_func)
        self.tree.append_column(col)
        self.podcasts = {}
        self.drivers = {}
        self.driver_names = {}
        self.__dragging = False

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.tree.set_model(self.model)

        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.track = gtk.gdk.pixbuf_new_from_file('images%strack.png' %
            os.sep)
        self.folder = xlmisc.get_icon('gnome-fs-directory')
        self.refresh_image = xlmisc.get_icon('gtk-refresh')

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

        self.tree.expand_row(self.model.get_path(self.custom), False)
        self.tree.expand_row(self.model.get_path(self.podcast), False)

        self.radio_root = self.model.append(None, [self.open_folder, "Radio "
            "Streams"])

        self.drivers_expanded = {}
        self.load_nodes = {}
        self.tree.connect('row-expanded', self.on_row_expand)
        self.tree.connect('button-press-event', self.button_pressed)
        self.tree.connect('button-release-event', self.button_release)
        self.tree.connect('row-collapsed', self.on_collapsed)
        self.tree.connect('button-press-event', self.button_pressed)
        self.tree.connect('button-release-event', self.button_release)
        self.__dragging = False
        self.xml.get_widget('pradio_add_button').connect('clicked',
            self.on_add_station)
        self.xml.get_widget('pradio_remove_button').connect('clicked',
            self.remove_station)
        self.podcast_download_box = \
            self.xml.get_widget('ppodcast_download_box')
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

            if isinstance(object, CustomWrapper):
                self.cmenu.popup(None, None, None,
                    event.button, event.time)

            elif isinstance(object, PRadioDriver) or isinstance(object,
                PRadioGenre):
                self.menu.popup(None, None, None, event.button, event.time)
            else:
                if object == "Saved Stations" or \
                    object == "Podcasts" or \
                    object == "Shoutcast Stations":
                    return
#                self.menu.popup(None, None, None,
#                    event.button, event.time)
            
        elif event.type == gtk.gdk._2BUTTON_PRESS:
            if object == 'Last.FM Radio':
                self.tree.expand_row(path, False)                
            elif isinstance(object, CustomWrapper):
                self.open_station(object.name)
            elif isinstance(object, PodcastWrapper):
                self.open_podcast(object)
            elif isinstance(object, LastFMWrapper):
                self.open_lastfm(object)
            elif isinstance(object, PRadioGenre):
                if object.driver:
                    tracks = trackslist.TracksListCtrl(self.exaile)
                    self.exaile.playlists_nb.append_page(tracks,
                        xlmisc.NotebookTab(self.exaile, str(object), tracks))
                    self.exaile.playlists_nb.set_current_page(
                        self.exaile.playlists_nb.get_n_pages() - 1)
                    self.exaile.tracks = tracks
                    object.driver.tracks = tracks
                    object.driver.load_genre(object)
            return True

    def cell_data_func(self, column, cell, model, iter, user_data=None):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        if isinstance(object, CustomWrapper):
            cell.set_property('text', str(object))
        else:
            cell.set_property('text', str(object))

    def add_driver(self, driver, name):
        """
            Adds a driver to the list of drivers
        """
        if not self.drivers.has_key(driver):
            driver.name = name
            self.driver_names[driver] = name
            node = self.model.append(self.radio_root, [self.folder, driver])

            self.load_nodes[driver] = self.model.append(node, 
                [self.refresh_image, "Loading streams..."])
            self.drivers[driver] = node
            self.tree.expand_row(self.model.get_path(self.radio_root), False)
            if self.exaile.settings.get_boolean('row_expanded', plugin=name,
                default=False):
                self.tree.expand_row(self.model.get_path(node), False)

    def remove_driver(self, driver):
        """
            Removes a radio driver
        """
        if self.drivers.has_key(driver):
            self.model.remove(self.drivers[driver])
            del self.drivers[driver]

    def open_lastfm(self, object):
        """
            Opens and plays a last.fm station
        """
        station = str(object)
        user = self.exaile.settings.get_str('lastfm/user', '')
        password = self.exaile.settings.get_crypted('lastfm/pass', '')

        if not user or not password:
            common.error(self.exaile.window, _("You need to have a last.fm "
                "username and password set in your preferences."))
            return

        if station == "Neighbor Radio":
            url = "lastfm://user/%s/neighbours" % user
        else:
            url = "lastfm://user/%s/personal" % user

        tr = media.Track(url)
        tr.type = 'lastfm'
        tr.track = -1
        tr.title = station
        tr.album = "%s's Last.FM %s" % (user, station)


        self.exaile.append_songs((tr,))

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
                'loc': row[0],
                'year': row[4], 
                'length': row[3], 
            })

            song = media.Track()
            song.set_info(**info)
            song.type = 'podcast'
            song.size = row[5]

            (download_path, downloaded) = \
                self.get_podcast_download_path(row[0])
            add_item = False

            if not self.exaile.settings.get_boolean('download_feeds', True):
                add_item = False

                song.download_path = 1
            else:
                if not downloaded:

                    song.artist = "Not downloaded"
                    song.download_path = ''
                    add_item = True
                else:
                    song.download_path = download_path

            song.length = row[3]
            song.podcast_path = wrapper.path
            songs.append(song)
            self.podcasts[song.loc] = song
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
        driver = self.model.get_value(iter, 1)
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.model.set_value(iter, 0, self.folder)
        self.tree.queue_draw()
        self.exaile.settings.set_boolean('row_expanded', False,
            plugin=self.driver_names[driver])

    def on_row_expand(self, treeview, iter, path):
        """
            Called when the user clicks on a row to expand the stations under
        """
        driver = self.model.get_value(iter, 1)
        self.model.set_value(iter, 0, self.open_folder)
        self.tree.queue_draw()

        if not isinstance(driver, PRadioDriver): return
        if self.drivers.has_key(driver) and not \
            self.drivers_expanded.has_key(driver):
            self.drivers_expanded[driver] = 1

            driver.load_streams(self.drivers[driver],
                self.load_nodes[driver]) 
        self.exaile.settings.set_boolean('row_expanded', True,
            plugin=self.driver_names[driver])

    def setup_menus(self):
        """
            Create the two different popup menus associated with this tree.
            There are two menus, one for saved stations, and one for
            shoutcast stations
        """
        self.menu = xlmisc.Menu()
        rel = self.menu.append(_("Refresh"), lambda e, f:
            self.refresh_streams())

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

    def refresh_streams(self):
        """
            Refreshes the streams for the currently selected driver
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        object = self.model.get_value(iter, 1)
        if isinstance(object, PRadioDriver):
            driver = object
            self.drivers_expanded[driver] = 1
            self.clean_node(self.drivers[driver])
            self.load_nodes[driver] = self.model.append(iter, 
                [self.refresh_image, "Loading streams..."])
            driver.load_streams(self.drivers[driver], 
                self.load_nodes[driver], False)
            self.tree.expand_row(self.model.get_path(iter), False)
        elif isinstance(object, PRadioGenre):
            if object.driver:
                tracks = trackslist.TracksListCtrl(self.exaile)
                self.exaile.playlists_nb.append_page(tracks,
                    xlmisc.NotebookTab(self.exaile, str(object), tracks))
                self.exaile.playlists_nb.set_current_page(
                    self.exaile.playlists_nb.get_n_pages() - 1)
                self.exaile.tracks = tracks
                object.driver.tracks = tracks
                object.driver.load_genre(object, rel=True)

    def clean_node(self, node):
        """
            Cleans a node of all it's children
        """
        iter = self.model.iter_children(node)
        while True:
            if not iter: break
            self.model.remove(iter)
            iter = self.model.iter_children(node)

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

    @common.threaded
    def refresh_podcast(self, path, item):
        """
            Refreshes a podcast
        """
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
            _("Are you sure you want to permanently delete the selected "
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
            info['artist'] = row[2]
            info['album'] = row[1]
            info['loc'] = row[2]
            info['title'] = row[0]
            info['bitrate'] = row[3]

            track = media.Track()
            track.set_info(**info)
            track.type = 'stream'
            songs.append(track)
        tracks.playlist = playlist
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

            c = self.db.record_count("radio", "name=?", (name,))

            if c > 0:
                common.error(self.exaile.window, _("Station name already exists."))
                return
            radio_id = tracks.get_column_id(self.db, 'radio', 'name', name)
            path_id = tracks.get_column_id(self.db, 'paths', 'name', url)
            self.db.execute("INSERT INTO radio_items(radio, path, title, "
                "description) VALUES( ?, ?, ?, ? )", (radio_id, path_id, desc,
                desc))
            
            item = self.model.append(self.custom, [self.track, 
                CustomWrapper(name)])
            path = self.model.get_path(self.custom)
            self.tree.expand_row(path, False)

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
            if track.type != 'stream': continue
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

        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)

    def load_playlists(self):
        """
            Loads the playlists
        """
        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.tree.set_model(self.model)
        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.playlist_image = gtk.gdk.pixbuf_new_from_file('images%splaylist.png' % os.sep)
        self.smart_image = self.exaile.window.render_icon('gtk-execute',
            gtk.ICON_SIZE_MENU)
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
        
        rows = self.db.select("SELECT name, id, type FROM playlists ORDER BY"
            " name")
        for row in rows:
            if not row[2]:
                self.model.append(self.custom, [self.playlist_image, row[0],
                    CustomPlaylist(row[0], row[1])])
            elif row[2] == 1:
                self.model.append(self.smart, [self.smart_image, row[0],
                    SmartPlaylist(row[0], row[1])])

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
        self.edit_item = self.menu.append('Edit', self.edit_playlist, 'gtk-edit')
        self.menu.append_separator()
        self.remove_item = self.menu.append('Delete Playlist', 
            self.remove_playlist,
            'gtk-remove')

    def edit_playlist(self, item, event):
        """
            Edits a playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()

        obj = model.get_value(iter, 2)
        if not isinstance(obj, SmartPlaylist): return
        row = self.db.read_one('playlists', 'matchany', 
            'id=?', (obj.id,))

        dialog = filtergui.FilterDialog('Edit Playlist', CRITERIA)
        dialog.set_transient_for(self.exaile.window)

        dialog.set_name(obj.name)
        dialog.set_match_any(row[0])

        state = []
        rows = self.db.select('SELECT crit1, crit2, filter FROM '
            'smart_playlist_items WHERE playlist=? ORDER BY line',
            (obj.id,))

        for row in rows:
            left = [row[0], row[1]]
            filter = eval(row[2])
            if len(filter) == 1:
                filter = filter[0]
            state.append((left, filter))

        print repr(state)

        dialog.set_state(state)

        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_ACCEPT:
            name = dialog.get_name()
            if name != obj.name:
                row = self.db.read_one('playlists', 'matchany', 
                    'name=?', (name,))
                if row:
                    common.error(self.exaile.window, _("That playlist name "
                        "is already taken."))
                    return
            matchany = dialog.get_match_any()
            self.db.execute('UPDATE playlists SET name=?, matchany=? WHERE '
                'id=?', (name, matchany, obj.id))
            self.db.execute('DELETE FROM smart_playlist_items WHERE '
                'playlist=?', (obj.id,))

            count = 0
            for c, v in dialog.get_state():
                if type(v) != list:
                    v = list((v,))
                self.db.execute("INSERT INTO smart_playlist_items( "
                    "playlist, line, crit1, crit2, filter ) VALUES( "
                    " ?, ?, ?, ?, ? )", (obj.id, count, c[0], c[1],
                    repr(v)))
                count += 1

            self.db.commit()
            self.model.set_value(iter, 1, name)
            self.model.set_value(iter, 2, SmartPlaylist(name, obj.id))

        dialog.destroy()

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
            matchany = dialog.get_match_any()
            if not name: 
                common.error(self.exaile.window, _("You did not enter a "
                    "name for your playlist"))
                return
            row = self.db.read_one('playlists', 'name', 'name=?', (name,))
            if row:
                common.error(self.exaile.window, _("That playlist name "
                    "is already taken."))
                return

            self.db.execute("INSERT INTO playlists( name, type, matchany "
                ") VALUES( ?, 1, ? )", (name, matchany))
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

            self.model.append(self.smart, [self.smart_image, name, 
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
        edit_enabled = False
        if self.tree.get_path_at_pos(x, y):
            (path, col, x, y) = self.tree.get_path_at_pos(x, y)
            iter = self.model.get_iter(path)
            obj = self.model.get_value(iter, 2)
            self.edit_item.set_sensitive(edit_enabled)
            if isinstance(obj, CustomPlaylist) or \
                isinstance(obj, SmartPlaylist):
                delete_enabled = True
            if isinstance(obj, SmartPlaylist):
                edit_enabled = True

        self.remove_item.set_sensitive(delete_enabled)
        self.edit_item.set_sensitive(edit_enabled)

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
            playlist_id = tracks.get_column_id(self.db, 'playlists', 'name', playlist)

            rows = self.db.select('SELECT paths.name FROM playlist_items,paths '
                'WHERE playlist_items.path=paths.id AND playlist=?',
                (playlist_id,))

            songs = tracks.TrackData()
            for row in rows:
                tr = tracks.read_track(self.db, self.exaile.all_songs, row[0])
                if tr:
                    songs.append(tr)

            self.playlist_songs = songs
            self.exaile.new_page(playlist, self.playlist_songs)
            self.exaile.on_search()
            self.exaile.tracks.playlist = playlist

    def open_smart_playlist(self, name, id):
        """
            Opens a smart playlist
        """
        row = self.db.read_one('playlists', 'matchany', 'id=?', (id,))
        rows = self.db.select("SELECT crit1, crit2, filter FROM "
            "smart_playlist_items WHERE playlist=? ORDER BY line", (id,))

        where = []
        andor = " AND "
        if row[0]: andor = ' OR '

        state = []

        for row in rows:
            left = [row[0], row[1]]
            filter = eval(row[2])
            if len(filter) == 1:
                filter = filter[0]
            state.append((left, filter))

        filter = filtergui.FilterWidget(CRITERIA)
        filter.set_state(state)
        where = filter.get_result()

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
            m = re.search(r'^device_(\w+)://', l)
            if m:
                continue
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
        if not isinstance(obj, CustomPlaylist) and \
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
                table = 'smart_playlist_items'
            self.db.execute("DELETE FROM %s WHERE playlist=?" % table,
                (p_id,))
            if tracks.PLAYLISTS.has_key(playlist):
                del tracks.PLAYLISTS[playlist]
            self.db.commit()
            
            self.model.remove(iter)
        dialog.destroy()

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
            if track.type == 'stream': continue
            path_id = tracks.get_column_id(self.db, 'paths', 'name', track.loc)
            self.db.execute("INSERT INTO playlist_items( playlist, path ) " \
                "VALUES( ?, ? )", (playlist_id, path_id))
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
        self.first_dir = self.exaile.settings.get_str('files_panel_dir',
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

        # set up the search entry
        self.search = self.xml.get_widget('files_search_entry')
        self.search.connect('key-release-event', self.key_release)
        self.search.connect('activate', lambda *e:
            self.load_directory(self.current, history=False,
            keyword=self.search.get_text()))

        self.key_id = None

        self.load_directory(self.first_dir, False)
        self.tree.connect('row-activated', self.row_activated)
        self.menu = xlmisc.Menu()
        self.menu.append(_("Append to Playlist"), self.append)
        self.queue_item = self.menu.append(_("Queue Items"), self.append)

    def key_release(self, *e):
        """
            Called when someone releases a key.
            Sets up a timer to simulate live-search
        """
        if self.key_id:
            gobject.source_remove(self.key_id)
            self.key_id = None

        self.key_id = gobject.timeout_add(700, lambda *e:
            self.load_directory(self.current, history=False,
            keyword=self.search.get_text()))

    def drag_get_data(self, treeview, context, sel, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """

        songs = self.get_selected_songs()
        uris = [urllib.quote(song.loc.encode(xlmisc.get_default_encoding())) for song in songs]

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
        self.exaile.status.set_first(_("Scanning and adding files..."))
        songs = self.get_selected_songs()
        if songs:
            self.exaile.append_songs(songs, queue=(widget == self.queue_item),
                play=False)
        self.counter = 0
        self.exaile.status.set_first(None)

    def get_selected_songs(self):
        """
            Appends recursively the selected directory/files
        """
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
            elif ext.lower() in media.SUPPORTED_MEDIA:
                tr = self.get_track(value)
                if tr:
                    songs.append(tr)

        if songs:
            # sort the songs
            ar = [(song.artist, song.album, song.track, song.title, song)
                for song in songs]
            ar.sort()
            songs = [item[-1] for item in ar]
            return songs
        else:
            return None

    def get_track(self, path):
        """
            Gets a track
        """
        tr = tracks.read_track(self.exaile.db, self.exaile.all_songs, path)
        return tr

    def append_recursive(self, songs, dir):
        """
            Appends recursively
        """
        for file in os.listdir(dir):
            if os.path.isdir(os.path.join(dir, file)):
                self.append_recursive(songs, os.path.join(dir, file))
            else:
                (stuff, ext) = os.path.splitext(file)
                if ext.lower() in media.SUPPORTED_MEDIA:
                    tr = self.get_track(os.path.join(dir, file))
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
        if dir.startswith('~'):
            dir = os.getenv('HOME', '~') + dir[1:]
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
                        self.exaile.append_songs((tr, ))

    def load_directory(self, dir, history=True, keyword=None):
        """
            Loads a directory into the files view
        """
        try:
            paths = os.listdir(dir)
        except OSError:
            dir = os.getenv('HOME')
            paths = os.listdir(dir)

        self.exaile.settings['files_panel_dir'] = dir
        self.current = dir
        directories = []
        files = []
        for path in paths:
            if path.startswith('.'): continue

            if keyword and path.lower().find(keyword.lower()) == -1:
                continue
            full = "%s%s%s" % (dir, os.sep, path)
            if os.path.isdir(full):
                directories.append(path)

            else:
                (stuff, ext) = os.path.splitext(path)
                if ext.lower() in media.SUPPORTED_MEDIA:
                    files.append(path)

        directories.sort()
        files.sort()

        self.model.clear()
        
        for d in directories:
            self.model.append([self.directory, d, '-'])

        for f in files:
            try:
                info = os.stat("%s%s%s" % (dir, os.sep, f))
            except OSError:
                continue
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
