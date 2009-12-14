# Copyright (C) 2008-2009 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import logging
import traceback
import urllib

import gobject
import gtk

from xl.nls import gettext as _
from xl import event, xdg, common, metadata, settings, trax
import xlgui
from xlgui import panel, guiutil, menu, playlist, rating

logger = logging.getLogger(__name__)

TRACK_NUM = 300

# TODO: come up with a more customizable way to handle this
SEARCH_TAGS = ("artist", "albumartist", "album", "title")

def first_meaningful_char(s):
    for i in range(len(s)):
        if s[i].isdigit():
            return '0'
        elif s[i].isalpha():
            return s[i]
    return '_'

class TreeLevelTabs(object):
    def __init__(self, level):

        if type(level) is str:
            self.__tags = [level]
            self.__printList = [0]
            self.__searchedTagsIndices = [0]
            return
        if type(level) is tuple:
            self.__tags = level[0]
            self.__printList = level[1]
            self.__searchedTagsIndices = level[2]
            return

    def printTags(self, tagsValues):
        return ''.join([(tagsValues[x] if type(x) is int else x) for x in self.__printList])

    def tags(self):
        return self.__tags

    def searchedTagsIndices(self):
        return self.__searchedTagsIndices

def get_all_tags(order):
    result = []
    for level in order:
        result.extend(level.tags())
    return result

class CollectionPanel(panel.Panel):
    """
        The collection panel
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'collection-tree-loaded': (gobject.SIGNAL_RUN_LAST, None, ()),
    }

    ui_info = ('collection_panel.ui', 'CollectionPanelWindow')
    """
        Each level in order is a tuple of tree lists
        First list is list of tags, that are relevant to this level, in their sort order
        Second list describes way of node is printed. Strings in list remain the same,
        and values of corresponding tags are inserted instead of integers
        Third list is list of indices of tags that tracks are searched by
        If level is string 'tag', it's the same as (['tag'], [0], [0])
    """
    orders = (
        ['artist', 'album', (['discnumber', 'tracknumber', 'title'], [2], [2])],
        ['album', (['discnumber', 'tracknumber', 'title'], [2], [2])],
        ['genre', 'artist', 'album', (['discnumber', 'tracknumber', 'title'], [2], [2])],
        ['genre', 'album', 'artist', (['discnumber', 'tracknumber', 'title'], [2], [2])],
        ['date', 'artist', 'album', (['discnumber', 'tracknumber', 'title'], [2], [2])],
        ['date', 'album', 'artist', (['discnumber', 'tracknumber', 'title'], [2], [2])],
        ['artist', (['date', 'album'], [0, ' - ', 1], [0, 1]), (['discnumber', 'tracknumber', 'title'], [2], [2])],
    )

    def __init__(self, parent, collection, name=None,
        _show_collection_empty_message=False):
        """
            Initializes the collection panel

            @param parent: the parent dialog
            @param collection: the xl.collection.Collection instance
            @param name: an optional name for this panel
        """
        panel.Panel.__init__(self, parent, name)

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

        self.menu = menu.CollectionPanelMenu(self.tree.get_selection(),
            self.get_selected_tracks,
            self.get_tracks_rating)
        self.menu.connect('append-items', lambda *e:
            self.emit('append-items', self.get_selected_tracks()))
        self.menu.connect('queue-items', lambda *e:
            self.emit('queue-items', self.get_selected_tracks()))
        self.menu.connect('rating-set', self._on_set_rating)
        self.menu.connect('delete-items', self._on_delete_items)
        self.menu.connect('properties', lambda *e:
            self.properties_dialog())


        self.load_tree()

    def properties_dialog(self):
        """
            Shows the properties dialog
        """
        from xlgui import properties
        tracks = self.get_selected_tracks()

        if not tracks:
            return False

        tracks = trax.sort_tracks(
			('artist', 'date', 'album', 'discnumber', 'tracknumber'),
			tracks)

        dialog = properties.TrackPropertiesDialog(self.parent,
            tracks)

    def _on_set_rating(self, widget, new_rating):
        """
            Called when a new rating is chosen from the rating menu
        """
        tracks = self.get_selected_tracks()
        rating.set_rating(tracks, new_rating)

    def _on_delete_items(self, *args):
        dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_YES_NO,
                message_format=_("This will permanantly delete the selected "
                    "tracks from your disk, are you sure you wish to continue?")
                )
        res = dialog.run()
        if res == gtk.RESPONSE_YES:
            tracks = self.get_selected_tracks()
            self.collection.delete_tracks(tracks)

        dialog.destroy()
        gobject.idle_add(self.load_tree)


    def _setup_widgets(self):
        """
            Sets up the various widgets to be used in this panel
        """
        self.choice = self.builder.get_object('collection_combo_box')
        active = settings.get_option('gui/collection_active_view', 0)
        self.choice.set_active(active)

        self.filter = guiutil.SearchEntry(
            self.builder.get_object('collection_search_entry'))

    def _check_collection_empty(self, *e):
        if not self._show_collection_empty_message or \
            (self.collection.libraries and self.collection_empty_message):
            self.collection_empty_message = False
            self.vbox.set_child_visible(True)
            self.message.set_child_visible(False)
            self.vbox.show_all()
            self.message.hide_all()

        elif not self.collection.libraries and not self.collection_empty_message:
            self.collection_empty_message = True
            self.vbox.set_child_visible(False)
            self.message.set_no_show_all(False)
            self.message.set_child_visible(True)
            self.vbox.hide_all()
            self.message.show_all()

    def _connect_events(self):
        """
            Uses signal_autoconnect to connect the various events
        """
        self.builder.connect_signals({
            'on_collection_combo_box_changed': lambda *e: self.load_tree(),
            'on_refresh_button_pressed': self.on_refresh_button_pressed,
            'on_refresh_button_key_pressed': self.on_refresh_button_key_pressed,
            'on_collection_search_entry_activate': self.on_collection_search_entry_activate,
            'on_empty_collection_button_clicked': lambda *x: xlgui.controller().collection_manager()
        })
        self.tree.connect('key-release-event', self.on_key_released)
        event.add_callback(self.refresh_tags_in_tree, 'track_tags_changed')

    def on_refresh_button_pressed(self, button, event):
        """
            Called on mouse activation of the refresh button
        """
        if event.button == 3:
            menu = guiutil.Menu()
            menu.append(_('Rescan Collection'),
                xlgui.controller().on_rescan_collection,
                'gtk-refresh')
            menu.popup(None, None, None, event.button, event.time)
            return

        if event.state & gtk.gdk.SHIFT_MASK:
            xlgui.controller().on_rescan_collection(None)
        else:
            self.load_tree()

    def on_refresh_button_key_pressed(self, widget, event):
        """
            Called on key presses on the refresh button
        """
        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname != 'Return': return False

        if event.state & gtk.gdk.SHIFT_MASK:
            xlgui.controller().on_rescan_collection(None)
        else:
            self.load_tree()

    def on_key_released(self, widget, event):
        """
            Called when a key is released in the tree
        """
        if event.keyval == gtk.keysyms.Menu:
            gtk.Menu.popup(self.menu, None, None, None, 0, event.time)
            return True

        if event.keyval == gtk.keysyms.Left:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            for path in paths:
                self.tree.collapse_row(path)
            return True

        if event.keyval == gtk.keysyms.Right:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            for path in paths:
                self.tree.expand_row(path, False)
            return True

        if event.keyval == gtk.keysyms.Return:
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

    def _setup_images(self):
        """
            Sets up the various images that will be used in the tree
        """
        window = gtk.Window()
        self.artist_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path("images/artist.png"))
        self.date_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/year.png'))
        self.album_image = window.render_icon('gtk-cdrom',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.title_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/track.png'))
        self.genre_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/genre.png'))

    def drag_data_received(self, *e):
        """
            stubb
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
        trs = self.get_selected_tracks()
        for track in trs:
            guiutil.DragTreeView.dragged_data[track.get_loc_for_io()] = track
        urls = guiutil.get_urls_for(trs)
        selection.set_uris(urls)

    def _setup_tree(self):
        """
            Sets up the tree widget
        """
        self.tree = guiutil.DragTreeView(self)
        self.tree.set_headers_visible(False)
        container = self.builder.get_object('CollectionPanel')
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
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)

        if settings.get_option('gui/ellipsize_text_in_panels', False):
            import pango
            cell.set_property('ellipsize-set', True)
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            self.tree.set_tooltip_column(1)

        self.tree.set_row_separator_func(
            lambda m, i: m.get_value(i, 1) is None)

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.model_blank = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)

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

    def get_selected_tracks(self):
        """
            Finds all the selected tracks
        """

        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        trs = []
        for path in paths:
            iter = self.model.get_iter(path)
            newset = self._find_tracks(iter)
            trs.append(newset)

        if not trs: return None

        trs = list(set(reduce(lambda x, y: list(x) + list(y), trs)))

        return trs

    def get_tracks_rating(self):
        """
            Returns the rating of the selected tracks
            Returns 0 if there is no selection, if tracks have different ratings
            or if the selection is too big
        """
        rating = 0
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        tracks_limit = settings.get_option('miscellaneous/rating_widget_tracks_limit', 0)
        if tracks_limit == 0: return 0
        current_count = 0

        if paths and paths[0]:
            iter = self.model.get_iter(paths[0])
            newset = self._find_tracks(iter)
            current_count += len (newset)
            if current_count > tracks_limit:
                return 0 # too many tracks

            if newset and newset[0]:
                rating = newset[0].get_rating ()

            if rating == 0:
                return 0 # if first song has 0 as a rating, we know the result

            for song in newset:
                if song.get_rating() != rating:
                    return 0 # different ratings
        else:
            return 0 # no tracks

        for path in paths[1:]:
            iter = self.model.get_iter(path)
            newset = self._find_tracks(iter)
            current_count += len (newset)
            if current_count > tracks_limit:
                return 0 # too many tracks

            for song in newset:
                if song.get_rating() != rating:
                    return 0 # different ratings

        return rating # only one rating in the tracks, returning it

    def append_to_playlist(self, item=None, event=None):
        """
            Adds items to the current playlist
        """
        self.emit('append-items', self.get_selected_tracks())

    def button_press(self, widget, event):
        """
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        (x, y) = map(int, event.get_coords())
        path = self.tree.get_path_at_pos(x, y)
        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.append_to_playlist()
            return False
        elif event.button == 3:
            self.menu.popup(event)
            if not path:
                return False
            (mods,paths) = selection.get_selected_rows()
            if (path[0] in paths):
                if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
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
        """
            wrapper so that multiple events dont cause multiple
            reloads in quick succession
        """
        if settings.get_option('gui/sync_on_tag_change', True) and \
            tag in get_all_tags(self.order):
            if self._refresh_id != 0:
                gobject.source_remove(self._refresh_id)
            self._refresh_id = gobject.timeout_add(500,
                    self._refresh_tags_in_tree)

    def _refresh_tags_in_tree(self):
        """
            Callback for when tags have changed and the tree
            needs reloading.
        """
        self.resort_tracks()
        self.load_tree()
        return False

    def resort_tracks(self):
#        import time
#        print "sorting...", time.clock()
        self.sorted_tracks = trax.sort_tracks(self.order[0].tags(), self.collection)
#        print "sorted.", time.clock()

    def load_tree(self):
        """
            Loads the gtk.TreeView for this collection panel.

            Loads tracks based on the current keyword, or all the tracks in
            the collection associated with this panel
        """
        self.current_start_count = self.start_count
        self.model.clear()
        self.tree.set_model(self.model_blank)

        self.root = None
        oldorder = self.order
        self.order = [TreeLevelTabs(x) for x in self.orders[self.choice.get_active()]]
        if oldorder != self.order:
            self.resort_tracks()

        # save the active view setting
        settings.set_option(
                'gui/collection_active_view',
                self.choice.get_active())

        keyword = self.keyword.strip()
        tags = list(SEARCH_TAGS)
        tags += [t for t in get_all_tags(self.order) if t != 'tracknumber' and t not in tags]

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
            gobject.idle_add(self._expand_node_by_name, search_num,
                parent, item, rest)

    def _expand_to(self, search_num, track, tmporder):
        """
            Expands to the specified track

            @param search_num: the current search id
            @param track: the track to expand
            @param tmporder: the ordering list
        """
        expand = []
        for item in tmporder:
            if search_num != self._search_num: return
            try:
                value = metadata.j(track[item])
                expand.append(value)
            except (TypeError, KeyError):
                continue

        if not expand: return

        # if we've already expanded this node, don't expand it again
        if tuple(expand) in self._expand_items: return
        self._expand_items.add(tuple(expand))

        gobject.idle_add(self._expand_node_by_name,
            search_num, None, item, expand)

    def _expand_search_nodes(self, search_num):
        """
            Expands the nodes in the tree that match the current search

            @param search_num: the current search id
        """
        if not self.keyword.strip(): return

        self._expand_items = set()
        for track in self.tracks:
            if search_num != self._search_num: return
            tmporder = self.order[:]
            if 'tracknumber' in tmporder: tmporder.remove('tracknumber')
            for item in reversed(tmporder):
                try:
                    value = metadata.j(track[item])
                    if not value: continue

                    if self.keyword.strip().lower() in value.lower():
                        self._expand_to(
                            search_num, track, tmporder)

                except (TypeError, KeyError):
                    traceback.print_exc()
                    continue

                tmporder.pop()

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
                self.model.get_value(self.model.iter_children(parent), 1) != None:
                previously_loaded = True
            iter_sep = self.model.iter_children(parent)
            depth = self.model.iter_depth(parent) + 1
        if previously_loaded:
            return

        search = self.get_node_search_terms(parent)

        try:
            tags = self.order[depth].tags()
            matchers = [trax.TracksMatcher(search)]
            srtrs = trax.search_tracks(self.tracks, matchers)
            # sort only if we are not on top level, because tracks are already sorted by fist order
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


        draw_seps = settings.get_option('gui/draw_separators', True)
        last_char = ''
        last_val = ''
        first = True
        path = None
        expanded = False
        to_expand = []

        for srtr in srtrs:
            stagvals = [srtr.track.get_tag_sort(x) for x in tags]
            stagval = self.order[depth].printTags(stagvals)
            if last_val != stagval:
                tagvals = [srtr.track.get_tag_display(x) for x in tags]
                tagval = self.order[depth].printTags(tagvals)
                last_val = stagval
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

                match_query = " ".join([
                    srtr.track.get_tag_search(t, format=True) for t in tags])
                iter = self.model.append(parent, [image, tagval, match_query])
                path = self.model.get_path(iter)
                expanded = False
                if not bottom:
                    self.model.append(iter, [None, None, None])

            if not expanded:
                alltags = []
                for o in self.order[depth+1:]:
                    alltags.extend(o.tags())
                for t in alltags:
                    if t in srtr.on_tags:
                        if depth > 0:
                            # for some reason, nested iters are always
                            # off by one in the terminal entry.
                            path = path[:-1] + (path[-1]-1,)
                        to_expand.append(path)
                        expanded = True

        if settings.get_option("gui/expand_enabled", True) and \
            len(to_expand) < \
                    settings.get_option("gui/expand_maximum_results", 100) and \
            len(self.keyword.strip()) >= \
                    settings.get_option("gui/expand_minimum_term_length", 2):
            for row in to_expand:
                gobject.idle_add(self.tree.expand_row, row, False)

        if iter_sep is not None:
            self.model.remove(iter_sep)



# vim: et sts=4 sw=4
