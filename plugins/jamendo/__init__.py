# Copyright (C) 2009-2010 Erin Drummond
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

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Gtk

from . import jamtree
from . import jamapi
from . import menu
import os
from xl import common, event, settings, providers, trax as xltrack
from xl.covers import CoverSearchMethod
from xl.nls import gettext as _
from xlgui import icons, panel
from xlgui.widgets.common import DragTreeView

JAMENDO_NOTEBOOK_PAGE = None
COVERS_METHOD = None


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def _enable(eventname, exaile, nothing):
    global JAMENDO_NOTEBOOK_PAGE, COVERS_METHOD

    user_agent = exaile.get_user_agent_string('jamendo')
    jamapi.set_user_agent(user_agent)

    JAMENDO_NOTEBOOK_PAGE = JamendoPanel(exaile.gui.main.window, exaile)
    COVERS_METHOD = JamendoCoverSearch(user_agent)
    providers.register('main-panel', JAMENDO_NOTEBOOK_PAGE)
    providers.register('covers', COVERS_METHOD)


def disable(exaile):
    global JAMENDO_NOTEBOOK_PAGE, COVERS_METHOD
    providers.unregister('main-panel', JAMENDO_NOTEBOOK_PAGE)
    providers.unregister('covers', COVERS_METHOD)


class JamendoPanel(panel.Panel):

    __gsignals__ = {
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'download-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    ui_info = (os.path.dirname(__file__) + "/ui/jamendo_panel.ui", 'JamendoPanel')

    def __init__(self, parent, exaile):
        panel.Panel.__init__(self, parent, 'jamendo', "Jamendo")

        self.parent = parent
        self.exaile = exaile

        self.STATUS_READY = _("Ready")
        self.STATUS_SEARCHING = _("Searching Jamendo catalogue...")
        self.STATUS_RETRIEVING_DATA = _("Retrieving song data...")

        self.setup_widgets()

    # find out whats selected and add the tracks under it to the playlist
    def add_to_playlist(self):
        sel = self.get_selected_item()
        if isinstance(sel, jamtree.Artist):
            if not sel.expanded:
                self.expand_artist(sel, True)
                return

            for album in sel.albums:
                if not album.expanded:
                    self.expand_album(album, True)
                    return

            for album in sel.albums:
                track_list = []
                for track in album.tracks:
                    track_list.append(track)
                self.add_tracks_to_playlist(track_list)

        if isinstance(sel, jamtree.Album):
            if not sel.expanded:
                self.expand_album(sel, True)
                return
            track_list = []
            for track in sel.tracks:
                track_list.append(track)
            self.add_tracks_to_playlist(track_list)

        if isinstance(sel, jamtree.Track):
            self.add_track_to_playlist(sel)

    # is called when the user wants to download something
    def download_selected(self):
        print(
            'It would be really cool if this worked, unfortunately I still need to implement it.'
        )

    # initialise the widgets
    def setup_widgets(self):
        # connect to the signals we listen for
        self.builder.connect_signals(
            {
                'search_entry_activated': self.on_search_entry_activated,
                'search_entry_icon_release': self.clear_search_terms,
                'refresh_button_clicked': self.on_search_entry_activated,
                'search_combobox_changed': self.on_search_combobox_changed,
                'ordertype_combobox_changed': self.on_ordertype_combobox_changed,
                'orderdirection_combobox_changed': self.on_orderdirection_combobox_changed,
                'results_combobox_changed': self.on_results_combobox_changed,
            }
        )

        # set up the rightclick menu
        self.menu = menu.JamendoMenu(self)

        # setup images
        self.artist_image = icons.MANAGER.pixbuf_from_icon_name(
            'artist', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.album_image = icons.MANAGER.pixbuf_from_icon_name(
            'media-optical', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.title_image = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR
        )

        # setup search combobox
        self.search_combobox = self.builder.get_object('searchComboBox')
        self.search_combobox.set_active(
            settings.get_option('plugin/jamendo/searchtype', 0)
        )

        # get handle on search entrybox
        self.search_textentry = self.builder.get_object('searchEntry')
        self.search_textentry.set_text(
            settings.get_option('plugin/jamendo/searchterms', "")
        )

        # setup order_by comboboxes
        self.orderby_type_combobox = self.builder.get_object('orderTypeComboBox')
        self.orderby_type_combobox.set_active(
            settings.get_option('plugin/jamendo/ordertype', 0)
        )
        self.orderby_direction_combobox = self.builder.get_object(
            'orderDirectionComboBox'
        )
        self.orderby_direction_combobox.set_active(
            settings.get_option('plugin/jamendo/orderdirection', 0)
        )

        # setup num_results combobox
        self.numresults_spinbutton = self.builder.get_object('numResultsSpinButton')
        self.numresults_spinbutton.set_value(
            settings.get_option('plugin/jamendo/numresults', 10)
        )

        # setup status label
        self.status_label = self.builder.get_object('statusLabel')
        self.set_status(self.STATUS_READY)

        # setup results treeview
        self.treeview = DragTreeView(self)
        self.treeview.connect("row-expanded", self.row_expanded)
        self.treeview.set_headers_visible(False)
        container = self.builder.get_object('treeview_box')
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.treeview)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        container.pack_start(scroll, True, True, 0)
        container.show_all()

        selection = self.treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        pb = Gtk.CellRendererPixbuf()
        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.treeview.append_column(col)

        self.model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, GObject.TYPE_PYOBJECT)
        self.treeview.set_model(self.model)

    def set_status(self, message):
        self.status_label.set_text(message)

    def on_search_combobox_changed(self, box, params=None):
        settings.set_option('plugin/jamendo/searchtype', box.get_active())

    def on_ordertype_combobox_changed(self, box, params=None):
        settings.set_option('plugin/jamendo/ordertype', box.get_active())

    def on_orderdirection_combobox_changed(self, box, params=None):
        settings.set_option('plugin/jamendo/orderdirection', box.get_active())

    def on_results_combobox_changed(self, box, params=None):
        settings.set_option('plugin/jamendo/numresults', box.get_active())

    # is called whenever the user expands a row in the TreeView
    def row_expanded(self, tree, iter, path):
        sel = self.get_selected_item()
        if not sel.expanded:
            # unexpand node, will get expanded once contents are loaded
            self.expand_node(sel, False)
            if isinstance(sel, jamtree.Artist):
                self.expand_artist(sel, False)

            if isinstance(sel, jamtree.Album):
                self.expand_album(sel, False)

            if isinstance(sel, jamtree.Track):
                self.add_track_to_playlist(sel)

    # Expand an artist node (fetch albums for that artist)
    # artist: The jamtree.Artist object you want to expand the node for
    # add_to_playlist: Whether or not add_to_playlist() should be called when done
    def expand_artist(self, artist, add_to_playlist=False):
        self.set_status(self.STATUS_RETRIEVING_DATA)
        artist.expanded = True
        jamapi_thread = jamapi.get_albums(
            artist, self.expand_artist_callback, add_to_playlist
        )
        jamapi_thread.start()

    # Callback function for when the jamapi thread started in expand_artist() completes
    # artist: The jamtree.Artist object that should have had its albums populated by the jamapi thread
    def expand_artist_callback(self, artist, add_to_playlist=False):
        self.remove_dummy(artist)
        for album in artist.albums:
            parent = self.model.append(
                artist.row_pointer, (self.album_image, album.name, album)
            )
            album.row_pointer = parent
            self.model.append(parent, (self.title_image, "", ""))
        if add_to_playlist:
            self.add_to_playlist()
        self.expand_node(artist)
        self.set_status(self.STATUS_READY)

    # Expand an Album node (fetch tracks for album)
    # album: the Album object to get tracks for
    # add_to_playlist: Whether or not add_to_playlist() should be called when done
    def expand_album(self, album, add_to_playlist=False):
        self.set_status(self.STATUS_RETRIEVING_DATA)
        album.expanded = True
        jamapi_thread = jamapi.get_tracks(
            album, self.expand_album_callback, add_to_playlist
        )
        jamapi_thread.start()

    # Callback function for when the jamapi thread started in expand_album() completes
    # album: The jamtree.Album object that should have had its tracks populated by the jamapi thread
    def expand_album_callback(self, album, add_to_playlist=False):
        self.remove_dummy(album)
        for track in album.tracks:
            parent = self.model.append(
                album.row_pointer, (self.title_image, track.name, track)
            )
            track.row_pointer = parent
        if add_to_playlist:
            self.add_to_playlist()
        self.expand_node(album)
        self.set_status(self.STATUS_READY)

    # removes the first child node of a node
    def remove_dummy(self, node):
        iter = node.row_pointer
        dummy = self.model.iter_children(iter)
        self.model.remove(dummy)

    # expands a TreeView node
    def expand_node(self, node, expand=True):
        iter = node.row_pointer
        path = self.model.get_path(iter)
        if expand:
            self.treeview.expand_row(path, False)
        else:
            self.treeview.collapse_row(path)

    # is called when a user doubleclicks an item in the TreeView
    def button_press(self, widget, event):

        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.add_to_playlist()

    # is called by the search thread when it completed
    def response_callback(self, collection):
        self.set_status(self.STATUS_READY)

        if collection is None:
            return

        for item in collection:
            # add item to treeview
            image = self.artist_image

            if isinstance(item, jamtree.Album):
                image = self.album_image
            if isinstance(item, jamtree.Track):
                image = self.title_image

            parent = self.model.append(None, (image, item.name, item))
            item.row_pointer = parent

            if not isinstance(item, jamtree.Track):
                self.model.append(parent, (self.artist_image, "", ""))

    # retrieve and display search results
    def on_search_entry_activated(self, widget):
        self.set_status(self.STATUS_SEARCHING)

        # clear existing search
        self.model.clear()

        # get type of search
        iter = self.search_combobox.get_active_iter()
        search_type = self.search_combobox.get_model().get_value(iter, 0)
        iter = self.orderby_type_combobox.get_active_iter()
        orderby = self.orderby_type_combobox.get_model().get_value(iter, 0)
        iter = self.orderby_direction_combobox.get_active_iter()
        direction = self.orderby_direction_combobox.get_model().get_value(iter, 0)
        orderby += "_" + direction
        numresults = self.numresults_spinbutton.get_value_as_int()
        search_term = self.search_textentry.get_text()

        # save search term
        settings.set_option('plugin/jamendo/searchterms', search_term)

        if search_type == 'artist':
            resultthread = jamapi.get_artist_list(
                search_term, orderby, numresults, self.response_callback
            )
            resultthread.start()

        if search_type == 'album':
            resultthread = jamapi.get_album_list(
                search_term, orderby, numresults, self.response_callback
            )
            resultthread.start()

        if search_type == 'genre_tags':
            resultthread = jamapi.get_artist_list_by_genre(
                search_term, orderby, numresults, self.response_callback
            )
            resultthread.start()

        if search_type == 'track':
            resultthread = jamapi.get_track_list(
                search_term, orderby, numresults, self.response_callback
            )
            resultthread.start()

    # clear the search box and results
    def clear_search_terms(self, entry, icon_pos, event):
        entry.set_text('')

    # get the Object (Artist, Album, Track) associated with the currently
    # selected item in the TreeView
    def get_selected_item(self):
        iter = self.treeview.get_selection().get_selected()[1]
        return self.model.get_value(iter, 2)

    # get the path for the currently selected item in the TreeView
    def get_selected_item_path(self):
        iter = self.treeview.get_selection().get_selected()[1]
        return self.model.get_path(iter)

    # get the type of an object
    def typeof(self, something):
        return something.__class__

    # add a track to the playlist based on its url.
    # track: a jamtree.Track object
    def add_track_to_playlist(self, track):
        self.add_tracks_to_playlist([track])

    # add a bunch of tracks to the playlist at once
    # track_list: a python list of jamtree.Track objects
    def add_tracks_to_playlist(self, track_list):
        # convert list to list of xl.Track objects as opposed to jamtree.Track objects
        xltrack_list = []
        for track in track_list:
            tr = xltrack.Track(track.url, scan=False)
            tr.set_tags(
                title=track.name, artist=track.artist_name, album=track.album_name
            )
            xltrack_list.append(tr)
        self.exaile.gui.main.get_selected_page().playlist.extend(xltrack_list)

    # dragdrop stuff
    def drag_data_received(self, *e):
        pass

    def drag_data_delete(self, *e):
        pass

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        self.add_to_playlist()


# The following is a custom CoverSearchMethod to retrieve covers from Jamendo
# It is designed to only to get covers for streaming tracks from jamendo


class JamendoCoverSearch(CoverSearchMethod):
    name = 'jamendo'
    use_cache = False  # do this since the tracks dont stay on local.
    fixed = True
    fixed_priority = 5  # take precendence, since we know we are 'right'
    # for matching tracks.

    def __init__(self, user_agent):
        self.user_agent = user_agent

    def find_covers(self, track, limit=-1):
        jamendo_url = track.get_loc_for_io()
        # http://stream10.jamendo.com/stream/61541/ogg2/02%20-%20PieRreF%20-%20Hologram.ogg?u=0&h=f2b227d38d
        split = jamendo_url.split('/')
        if len(split) > 5 and split[0] == 'http:' and split[2].endswith('.jamendo.com'):

            track_num = split[4]
            image_url = jamapi.get_album_image_url_from_track(track_num)

            if image_url:
                return [image_url]
        return []

    def get_cover_data(self, url):
        return common.get_url_contents(url, self.user_agent)
