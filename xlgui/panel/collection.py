# Copyright (C) 2008-2010 Adam Olsen
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
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
import itertools
import logging

from xl.nls import gettext as _
from xl import (
    common,
    event,
    formatter,
    settings,
    trax
)
import xlgui
from xlgui import (
    guiutil,
    icons,
    panel
)
from xlgui.panel import menus
from xlgui.widgets.common import DragTreeView
from xlgui.widgets import (
    info
)

logger = logging.getLogger(__name__)

# TODO: come up with a more customizable way to handle this
SEARCH_TAGS = ("artist", "albumartist", "album", "title")


def first_meaningful_char(s):
    for c in unicode(s):
        if c.isdigit():
            return '0'
        elif c.isalpha():
            return c
    else:
        return '_'

class Order(object):
    """
        An Order represents a structure for arranging Tracks into the
        Collection tree.

        It is based on a list of levels, which each take the form (("sort1",
        "sort2"), "$displaytag - $displaytag", ("search1", "search2")) wherin
        the first entry is a tuple of tags to use for sorting, the second a
        format string for xl.formatter, and the third a tuple of tags to use
        for searching.

        When passed in the paramters, a level can also be a single string
        instead of a tuple, and it will be treated equivalently to (("foo",),
        "$foo", ("foo",)) for some string "foo".
    """
    def __init__(self, name, levels, use_compilations=True):
        self.__name = name
        self.__levels = map(self.__parse_level, levels)
        self.__formatters = [formatter.TrackFormatter(l[1]) for l 
            in self.__levels]
        self.__use_compilations = use_compilations

    @staticmethod
    def __parse_level(val):
        if type(val) in (str, unicode):
            val = ((val,), "$%s"%val, (val,))
        return tuple(val)

    @property
    def name(self):
        return self.__name

    @property
    def use_compilations(self):
        return self.__use_compilations

    def get_levels(self):
        return self.__levels[:]

    def __len__(self):
        return len(self.__levels)

    def __eq__(self, other):
        self.__levels == other.get_levels()

    def all_sort_tags(self):
        return list(itertools.chain(*[l[0] for l in self.__levels]))

    def get_sort_tags(self, level):
        return list(self.__levels[level][0])

    def all_search_tags(self):
        return list(itertools.chain(*[l[2] for l in self.__levels]))

    def get_search_tags(self, level):
        return list(set(self.__levels[level][2]))

    def format_track(self, level, track):
        return self.__formatters[level].format(track)

DEFAULT_ORDERS = [
    (_("Artist"), 
        ("artist", "album", 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
    (_("Album"), 
        ("album", 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
    (_("Genre - Artist"), 
        ('genre', 'artist', 'album', 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
    (_("Genre - Album"), 
        ('genre', 'album', 'artist', 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
    (_("Date - Artist"), 
        ('date', 'artist', 'album', 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
    (_("Date - Album"), 
        ('date', 'album', 'artist', 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
    (_("Artist - (Date - Album)"), 
        ('artist', 
            (('date', 'album'), "$date - $album", ('date', 'album')), 
            (("discnumber", "tracknumber", "title"), "$title", ("title",)))),
        ]

class CollectionPanel(panel.Panel):
    """
        The collection panel
    """
    __gsignals__ = {
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'collection-tree-loaded': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    ui_info = ('collection.ui', 'CollectionPanelWindow')
    def __init__(self, parent, collection, name=None,
        _show_collection_empty_message=False, label=None):
        """
            Initializes the collection panel

            @param parent: the parent dialog
            @param collection: the xl.collection.Collection instance
            @param name: an optional name for this panel
        """
        panel.Panel.__init__(self, parent, name, label)

        self._show_collection_empty_message = _show_collection_empty_message
        self.collection = collection
        self.use_alphabet = settings.get_option('gui/use_alphabet', True)
        self.vbox = self.builder.get_object('CollectionPanel')
        self.message = self.builder.get_object('EmptyCollectionPanel')
        self.choice = self.builder.get_object('collection_combo_box')
        self.collection_empty_message = False
        self._search_num = 0
        self._refresh_id = 0
        self.start_count = 0
        self.keyword = ''
        self.orders = map(lambda x: Order(x[0], x[1]), DEFAULT_ORDERS)
        self._setup_tree()
        self._setup_widgets()
        self._check_collection_empty()
        self._setup_images()
        self._connect_events()
        self.order = None
        self.tracks = []
        self.sorted_tracks = []

        event.add_callback(self._check_collection_empty, 'libraries_modified',
            collection)

        self.menu = menus.CollectionContextMenu(self)

        self.load_tree()

    def _setup_widgets(self):
        """
            Sets up the various widgets to be used in this panel
        """
        self.choice = self.builder.get_object('collection_combo_box')
        self.choicemodel = self.builder.get_object('collection_combo_model')
        self.repopulate_choices()

        self.filter = guiutil.SearchEntry(
            self.builder.get_object('collection_search_entry'))

    def repopulate_choices(self):
        self.choice.set_model(None)
        self.choicemodel.clear()
        for order in self.orders:
            self.choicemodel.append([order.name])
        self.choice.set_model(self.choicemodel)
        # FIXME: use something other than index here, since index
        # doesn't deal well with dynamic lists...
        active = settings.get_option('gui/collection_active_view', 0)
        self.choice.set_active(active)

    def _check_collection_empty(self, *e):
        if not self._show_collection_empty_message or \
            (self.collection.libraries and self.collection_empty_message):
            self.collection_empty_message = False
            GLib.idle_add(self.vbox.set_child_visible, True)
            GLib.idle_add(self.message.set_child_visible, False)
            GLib.idle_add(self.vbox.show_all)
            GLib.idle_add(self.message.hide)

        elif not self.collection.libraries and not \
            self.collection_empty_message:
            self.collection_empty_message = True
            GLib.idle_add(self.vbox.set_child_visible, False)
            GLib.idle_add(self.message.set_no_show_all, False)
            GLib.idle_add(self.message.set_child_visible, True)
            GLib.idle_add(self.vbox.hide)
            GLib.idle_add(self.message.show_all)

    def _connect_events(self):
        """
            Uses signal_autoconnect to connect the various events
        """
        self.builder.connect_signals({
            'on_collection_combo_box_changed': lambda *e: self.load_tree(),
            'on_refresh_button_press_event': self.on_refresh_button_press_event,
            'on_refresh_button_key_press_event': 
                self.on_refresh_button_key_press_event,
            'on_collection_search_entry_activate': 
                self.on_collection_search_entry_activate,
            'on_add_music_button_clicked': self.on_add_music_button_clicked
        })
        self.tree.connect('key-release-event', self.on_key_released)
        event.add_callback(self.refresh_tags_in_tree, 'track_tags_changed')
        event.add_callback(self.refresh_tracks_in_tree, 
            'tracks_added', self.collection)
        event.add_callback(self.refresh_tracks_in_tree, 
            'tracks_removed', self.collection)

    def on_refresh_button_press_event(self, button, event):
        """
            Called on mouse activation of the refresh button
        """
        if event.button == 3:
            menu = guiutil.Menu()
            menu.append(_('Rescan Collection'),
                xlgui.get_controller().on_rescan_collection,
                Gtk.STOCK_REFRESH)
            menu.popup(None, None, None, None, event.button, event.time)
            return

        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            xlgui.get_controller().on_rescan_collection(None)
        else:
            self.load_tree()

    def on_refresh_button_key_press_event(self, widget, event):
        """
            Called on key presses on the refresh button
        """
        if event.keyval != Gdk.KEY_Return: return False

        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            xlgui.get_controller().on_rescan_collection(None)
        else:
            self.load_tree()

    def on_key_released(self, widget, event):
        """
            Called when a key is released in the tree
        """
        if event.keyval == Gdk.KEY_Menu:
            Gtk.Menu.popup(self.menu, None, None, None, None, 0, event.time)
            return True

        if event.keyval == Gdk.KEY_Left:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            for path in paths:
                self.tree.collapse_row(path)
            return True

        if event.keyval == Gdk.KEY_Right:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            for path in paths:
                self.tree.expand_row(path, False)
            return True

        if event.keyval == Gdk.KEY_Return:
            self.append_to_playlist()
            return True
        return False

    def on_collection_search_entry_activate(self, entry):
        """
            Searches tracks and reloads the tree
        """
        self.keyword = unicode(entry.get_text(), 'utf-8')
        self.start_count += 1
        self.load_tree()

    def on_add_music_button_clicked(self, button):
        xlgui.get_controller().collection_manager()

    def _setup_images(self):
        """
            Sets up the various images that will be used in the tree
        """
        self.artist_image = icons.MANAGER.pixbuf_from_icon_name(
            'artist', Gtk.IconSize.SMALL_TOOLBAR)
        self.date_image = icons.MANAGER.pixbuf_from_icon_name(
            'office-calendar', Gtk.IconSize.SMALL_TOOLBAR)
        self.album_image = icons.MANAGER.pixbuf_from_icon_name(
            'image-x-generic', Gtk.IconSize.SMALL_TOOLBAR)
        self.title_image = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR)
        self.genre_image = icons.MANAGER.pixbuf_from_icon_name(
            'genre', Gtk.IconSize.SMALL_TOOLBAR)

    def drag_data_received(self, *e):
        """
            stub
        """
        pass

    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        tracks = treeview.get_selected_tracks()

        for track in tracks:
            DragTreeView.dragged_data[track.get_loc_for_io()] = track

        uris = trax.util.get_uris_from_tracks(tracks)
        selection.set_uris(uris)

    def _setup_tree(self):
        """
            Sets up the tree widget
        """
        self.tree = CollectionDragTreeView(self)
        self.tree.set_headers_visible(False)
        container = self.builder.get_object('CollectionPanel')
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        container.pack_start(scroll, True, True, 0)
        container.show_all()

        selection = self.tree.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        pb = Gtk.CellRendererPixbuf()
        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)

        if settings.get_option('gui/ellipsize_text_in_panels', False):
            from gi.repository import Pango
            cell.set_property('ellipsize-set', True)
            cell.set_property('ellipsize', Pango.EllipsizeMode.END)

        self.tree.set_row_separator_func(
            (lambda m, i, d: m.get_value(i, 1) is None), None)

        self.model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, object)

        self.tree.connect("row-expanded", self.on_expanded)

    def _find_tracks(self, iter):
        """
            finds tracks matching a given iter.
        """
        self.load_subtree(iter)
        search = self.get_node_search_terms(iter)
        matcher = trax.TracksMatcher(search)
        srtrs = trax.search_tracks(self.tracks, [matcher])
        return [ x.track for x in srtrs ]

    def append_to_playlist(self, item=None, event=None, replace=False):
        """
            Adds items to the current playlist
        """
        if replace:
            self.emit('replace-items', self.tree.get_selected_tracks())
        else:
            self.emit('append-items', self.tree.get_selected_tracks(), True)

    def button_press(self, widget, event):
        """
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        (x, y) = map(int, event.get_coords())
        path = self.tree.get_path_at_pos(x, y)
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            replace = settings.get_option('playlist/replace_content', False)
            self.append_to_playlist(replace=replace)
            return False
        elif event.button == 2:
            self.append_to_playlist(replace=True)
            return False

    def button_release(self, widget, event):
        """
            Called when the user releases the mouse button on the tree
        """
        selection = self.tree.get_selection()
        (x, y) = map(int, event.get_coords())
        path = self.tree.get_path_at_pos(x, y)
        if event.button == 3:
            self.menu.popup(event)
            if not path:
                return False
            (mods,paths) = selection.get_selected_rows()
            if (path[0] in paths):
                if event.get_state() & (Gdk.ModifierType.SHIFT_MASK|Gdk.ModifierType.CONTROL_MASK):
                    return False
                return True
            else:
                return False

    def on_expanded(self, tree, iter, path):
        """
            Called when a user expands a tree item.

            Loads the various nodes that belong under this node.
        """
        self.load_subtree(iter)

    def get_node_search_terms(self, node):
        """
            Finds all the related search terms for a particular node
            @param node: the node you wish to create search terms
        """
        if not node:
            return ""

        queries = []
        while node:
            queries.append(self.model.get_value(node, 2))
            node = self.model.iter_parent(node)

        return " ".join(queries)

    def refresh_tags_in_tree(self, type, track, tag):
        if settings.get_option('gui/sync_on_tag_change', True) and \
            tag in self.order.all_sort_tags() and \
            self.collection.loc_is_member(track.get_loc_for_io()):
            self._refresh_tags_in_tree()

    def refresh_tracks_in_tree(self, type, obj, loc):
        GLib.idle_add(self._refresh_tags_in_tree)

    @common.glib_wait(500)
    def _refresh_tags_in_tree(self):
        """
            Callback for when tags have changed and the tree
            needs reloading.
        """
        # Trying to reload while we're rescanning is really inefficient,
        # so we delay it until we're done scanning.
        if self.collection._scanning:
            return True
        self.resort_tracks()
        self.load_tree()
        return False

    def resort_tracks(self):
#        import time
#        print "sorting...", time.clock()
        self.sorted_tracks = trax.sort_tracks(self.order.get_sort_tags(0),
            self.collection.get_tracks())
#        print "sorted.", time.clock()

    def load_tree(self):
        """
            Loads the Gtk.TreeView for this collection panel.

            Loads tracks based on the current keyword, or all the tracks in
            the collection associated with this panel
        """
        logger.debug("Reloading collection tree")
        self.current_start_count = self.start_count
        self.tree.set_model(None)
        self.model.clear()

        self.root = None
        oldorder = self.order
        self.order = self.orders[self.choice.get_active()]

        if not oldorder or oldorder != self.order:
            self.resort_tracks()

        # save the active view setting
        settings.set_option(
                'gui/collection_active_view',
                self.choice.get_active())

        keyword = self.keyword.strip()
        tags = list(SEARCH_TAGS)
        tags += self.order.all_search_tags()
        tags = list(set(tags)) # uniquify list to speed up search

        self.tracks = list(
                trax.search_tracks_from_string(self.sorted_tracks,
                    keyword, case_sensitive=False, keyword_tags=tags) )

        self.load_subtree(None)

        self.tree.set_model(self.model)

        self.emit('collection-tree-loaded')

    def _expand_node_by_name(self, search_num, parent, name, rest=None):
        """
            Recursive function to expand all nodes in a hierarchical list of
            names.

            @param search_num: the current search number
            @param parent: the parent node
            @param name: the name of the node to expand
            @param rest: the list of the nodes to expand after this one
        """
        iter = self.model.iter_children(parent)

        while iter:
            if search_num != self._search_num: return
            value = self.model.get_value(iter, 1)
            if not value:
                value = self.model.get_value(iter, 2)
            if value: value = unicode(value, 'utf-8')

            if value == name:
                self.tree.expand_row(self.model.get_path(iter), False)
                parent = iter
                break

            iter = self.model.iter_next(iter)

        if rest:
            item = rest.pop(0)
            GLib.idle_add(self._expand_node_by_name, search_num,
                parent, item, rest)

    def load_subtree(self, parent):
        """
            Loads all the sub nodes for a specified node

            @param node: the node
        """
        previously_loaded = False # was the subtree already loaded
        iter_sep = None
        if parent == None:
            depth = 0
        else:
            if self.model.iter_n_children(parent) != 1 or \
                self.model.get_value(
                    self.model.iter_children(parent), 1) != None:
                previously_loaded = True
            iter_sep = self.model.iter_children(parent)
            depth = self.model.iter_depth(parent) + 1
        if previously_loaded:
            return

        search = self.get_node_search_terms(parent)

        try:
            tags = self.order.get_sort_tags(depth)
            matchers = [trax.TracksMatcher(search)]
            srtrs = trax.search_tracks(self.tracks, matchers)
            # sort only if we are not on top level, because tracks are 
            # already sorted by fist order
            if depth > 0:
                srtrs = trax.sort_result_tracks(tags, srtrs)
        except IndexError:
            return # at the bottom of the tree
        try:
            image = getattr(self, "%s_image"%tags[-1])
        except:
            image = None
        bottom = False
        if depth == len(self.order)-1:
            bottom = True


        display_counts = settings.get_option('gui/display_track_counts', True)
        draw_seps = settings.get_option('gui/draw_separators', True)
        last_char = ''
        last_val = ''
        last_dval = ''
        last_matchq = ''
        count = 0
        first = True
        path = None
        expanded = False
        to_expand = []

        for srtr in srtrs:
            stagvals = [unicode(srtr.track.get_tag_sort(x)) for x in tags]
            stagval = " ".join(stagvals)
            if (last_val != stagval or bottom):
                tagval = self.order.format_track(depth, srtr.track)
                match_query = " ".join([
                    srtr.track.get_tag_search(t, format=True) for t in tags])
                if bottom:
                    match_query += " " + \
                            srtr.track.get_tag_search("__loc", format=True)

                # Different *sort tags can cause stagval to not match
                # but the below code will produce identical entries in
                # the displayed tree.  This condition checks to ensure
                # that new entries are added if and only if they will
                # display different results, avoiding that problem.
                if match_query != last_matchq or tagval != last_dval or bottom:
                    if display_counts and path and not bottom:
                        iter = self.model.get_iter(path)
                        val = self.model.get_value(iter, 1)
                        val = "%s (%s)"%(val, count)
                        self.model.set_value(iter, 1, val)
                        count = 0

                    last_val = stagval
                    last_dval = tagval
                    if depth == 0 and draw_seps:
                        val = srtr.track.get_tag_sort(tags[0])
                        char = first_meaningful_char(val)
                        if first:
                            last_char = char
                        else:
                            if char != last_char and last_char != '':
                                self.model.append(parent, [None, None, None])
                            last_char = char
                    first = False

                    last_matchq = match_query
                    iter = self.model.append(parent, 
                        [image, tagval, match_query])
                    path = self.model.get_path(iter)
                    expanded = False
                    if not bottom:
                        self.model.append(iter, [None, None, None])
            count += 1
            if not expanded:
                alltags = []
                for i in range(depth+1, len(self.order)):
                    alltags.extend(self.order.get_sort_tags(i))
                for t in alltags:
                    if t in srtr.on_tags:
                        # keep original path intact for following block
                        newpath = path
                        if depth > 0:
                            # for some reason, nested iters are always
                            # off by one in the terminal entry.
                            newpath = newpath[:-1] + (newpath[-1]-1,)
                        to_expand.append(newpath)
                        expanded = True

        if display_counts and path and not bottom:
            iter = self.model.get_iter(path)
            val = self.model.get_value(iter, 1)
            val = "%s (%s)"%(val, count)
            self.model.set_value(iter, 1, val)
            count = 0

        if settings.get_option("gui/expand_enabled", True) and \
            len(to_expand) < \
                    settings.get_option("gui/expand_maximum_results", 100) and \
            len(self.keyword.strip()) >= \
                    settings.get_option("gui/expand_minimum_term_length", 2):
            for row in to_expand:
                GLib.idle_add(self.tree.expand_row, row, False)

        if iter_sep is not None:
            self.model.remove(iter_sep)

class CollectionDragTreeView(DragTreeView):
    """
        Custom DragTreeView to retrieve data
        from collection tracks
    """
    def __init__(self, container, receive=False, source=True):
        """
            :param container: The container to place the TreeView into
            :param receive: True if the TreeView should receive drag events
            :param source: True if the TreeView should send drag events
        """
        DragTreeView.__init__(self, container, receive, source)

        self.set_has_tooltip(True)
        self.connect('query-tooltip', self.on_query_tooltip)
        # TODO: Make faster
        #self.tooltip = CollectionToolTip(self)

    def get_selection_empty(self):
        '''Returns True if there are no selected items'''
        return self.get_selection().count_selected_rows() == 0
        
    def get_selected_tracks(self):
        """
            Returns the currently selected tracks
        """
        model, paths = self.get_selection().get_selected_rows()
        tracks = []
        
        if len(paths) == 0:
            return tracks

        for path in paths:
            iter = model.get_iter(path)
            newset = self.container._find_tracks(iter)
            tracks.append(newset)
        
        tracks = list(set(reduce(lambda x, y: list(x) + list(y), tracks)))

        return trax.sort_tracks(common.BASE_SORT_TAGS, tracks)

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
            Sets up a basic tooltip
            Required to have "&" in tooltips working
        """
        if not widget.get_tooltip_context(x, y, keyboard_mode):
            return False

        result = widget.get_path_at_pos(x, y)
        if not result:
            return False
        
        path = result[0]

        model = widget.get_model()
        tooltip.set_text(model[path][1]) # 1: title
        widget.set_tooltip_row(tooltip, path)

        return True

class CollectionToolTip(info.TrackListToolTip):
    """
        Custom collection specific tooltip
    """
    def __init__(self, parent):
        """
            :param parent: the parent widget the tooltip
                should be attached to
        """
        info.TrackListToolTip.__init__(self, parent, display_tracklist=True)

    def on_query_tooltip(self, tree, x, y, keyboard_mode, tooltip):
        """
            Determines if the tooltip should be shown
            and feeds the required data to it
        """
        path = tree.get_path_at_pos(x, y)

        if path is None:
            return False

        path = path[0]
        model = tree.get_model()
        iter = model.get_iter(path)
        tracks = tree.container._find_tracks(iter)

        self.clear()
        self.set_tracklist(tracks)

        info.TrackListToolTip.on_query_tooltip(
            self, tree, x, y, keyboard_mode, tooltip)
        #tree.set_tooltip_row(tooltip, path)

        return True

# vim: et sts=4 sw=4
