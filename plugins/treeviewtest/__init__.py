# Copyright (C) 2010 Aren Olson
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

import gtk, gobject, pango
import collections
import os
from xl.nls import gettext as _
from xl import event, common, trax
from xlgui import guiutil, icons

WINDOW = None

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global WINDOW
    WINDOW = TestWindow(exaile)

def disable(exaile):
    global WINDOW
    WINDOW.destroy()
    WINDOW = None


class TestWindow(object):
    def __init__(self, exaile):
        self.exaile = exaile
        trs = exaile.collection
        pl = Playlist("test", trs)
        exaile.shortcut = pl
        self.window = gtk.Window()
        self.tabs = PlaylistNotebook()
        self.tabs.create_tab_from_playlist(pl)
        self.window.add(self.tabs)
        self.window.resize(800, 600)
        self.window.show_all()

    def destroy(self):
        self.window.destroy()

class SmartNotebook(gtk.Notebook):
    def __init__(self):
        gtk.Notebook.__init__(self)
        self.tab_menu_items = []

    def get_active_tab(self):
        pass

class PlaylistNotebook(SmartNotebook):
    def __init__(self):
        SmartNotebook.__init__(self)
        self._new_playlist_item = gtk.MenuItem(_("New Playlist"))
        self._new_playlist_item.connect('activate', self.create_new_playlist)
        self.tab_menu_items.append(self._new_playlist_item)

    def create_tab_from_playlist(self, playlist):
        page = PlaylistPage(playlist)
        tab = NotebookTab(self, page)
        self.append_page(page, tab)
        return tab

    def create_new_playlist(self, *args):
        pl = Playlist("Playlist")
        return self.create_tab_from_playlist(pl)


class NotebookTab(gtk.EventBox):
    """
        Class to represent a generic tab in a gtk.Notebook.

    """
    def __init__(self, notebook, page):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.notebook = notebook
        self.page = page
        page.set_tab(self)

        self.tab_menu_items = []

        self.connect('button_press_event', self.on_button_press)


        self.hbox = hbox = gtk.HBox(False, 2)
        self.add(hbox)

        self.icon = gtk.Image()
        self.icon.set_property("visible", False)
        hbox.pack_start(self.icon, False, False)

        self.label = gtk.Label("UNNAMED TAB")
        self.label.set_max_width_chars(20)
        self.label.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(self.label, False, False)

        self.button = button = gtk.Button()
        button.set_name("tabCloseButton")
        button.set_relief(gtk.RELIEF_NONE)
        button.set_focus_on_click(False)
        button.set_tooltip_text(_("Close tab"))
        button.connect('clicked', self.close)
        button.connect('button_press_event', self.on_button_press)
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        button.add(image)
        hbox.pack_end(button, False, False)

        self.show_all()

    def on_button_press(self, widget, event):
        if event.button == 3:
            menu = self._construct_menu()
            menu.show_all()
            menu.popup(None, None, None, event.button, event.time)
            menu.connect('deactivate', self._deconstruct_menu)
            return True
        elif event.button == 2:
            self.close()
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            pass
            # playlists have rename here
            # rename idea: replace label with textbox, edit in-place?

    def _deconstruct_menu(self, menu):
        children = menu.get_children()
        for c in children:
            menu.remove(c)

    def _construct_menu(self):
        menu = gtk.Menu()
        for item in self.notebook.tab_menu_items:
            menu.append(item)
        menu.append(gtk.SeparatorMenuItem())
        for item in self.page.tab_menu_items:
            menu.append(item)
        menu.append(gtk.SeparatorMenuItem())
        for item in self.tab_menu_items:
            menu.append(item)
        return menu

    def close(self, *args):
        if self.page.handle_close():
            self.notebook.remove_page(self.notebook.page_num(self.page))


class NotebookPage(object):
    def __init__(self):
        self.tab_menu_items = []
        self.tab = None

    def set_tab(self, tab):
        self.tab = tab

    def handle_close(self):
        """
            Called when the tab is about to be closed. This can be used to
            handle showing a save dialog or similar actions. Should return
            True if we're OK with continuing to close, or False to abort
            the close.
        """
        raise NotImplementedError

class PlaylistPage(gtk.VBox, NotebookPage):
    """
        Displays a playlist and associated controls.
    """
    def __init__(self, playlist):
        gtk.VBox.__init__(self)
        NotebookPage.__init__(self)
        self.playlist = playlist
        self._clear_menu_item = gtk.MenuItem(_("Clear All Tracks"))
        self._clear_menu_item.connect('activate', self.clear)
        self.tab_menu_items.append(self._clear_menu_item)


        uifile = os.path.join(os.path.dirname(__file__), "playlist.ui")
        self.builder = build = gtk.Builder()
        build.add_from_file(uifile)
        plpage = build.get_object("playlist_page")
        for child in plpage.get_children():
            plpage.remove(child)

        self.plwin = build.get_object("playlist_window")
        self.controls = build.get_object("controls_box")
        self.pack_start(self.plwin, True, True, padding=2)
        self.pack_start(self.controls, False, False, padding=2)

        self.view = guiutil.DragTreeView(self, drop_pos="between")
        self.plwin.add(self.view)
        self.shuffle_button = build.get_object("shuffle_button")
        self.repeat_button = build.get_object("repeat_button")
        self.dynamic_button = build.get_object("dynamic_button")


        self.model = PlaylistModel(playlist)
        self.view.set_rules_hint(True)
        self.view.set_enable_search(True)

        for idx, col in enumerate(self.model.columns):
            cell = gtk.CellRendererText()
            tvcol = gtk.TreeViewColumn(col, cell, text=idx)
            self.view.append_column(tvcol)

        self.view.set_model(self.model)
        self.view.connect("drag-drop", self.on_drag_drop)

        self.show_all()

    def handle_close(self):
        return True

    def clear(self, *args):
        self.playlist.clear()

    def get_selected_tracks(self):
        selection = self.view.get_selection()
        model, paths = selection.get_selected_rows()
        tracks = [model.get_track(path) for path in paths]
        return tracks

    def on_drag_drop(self, view, context, x, y, etime):
        self.drag_data_received(view, context, x, y,
                view.get_selection(), None, etime)
        context.finish(True, False)
        return True

    ### needed for DragTreeView ###

    def drag_data_received(self, view, context, x, y, selection, info, etime):
        print "data recieved"
        context.finish(True, False, etime)

    def drag_data_delete(self, view, context):
        print "data delete"
        pass

    def drag_get_data(self, view, context, selection, target_id, etime):
        print "get data"
        tracks = self.get_selected_tracks()
        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc_for_io()] = track

        uris = trax.get_uris_from_tracks(tracks)
        selection.set_uris(uris)

    def button_press(self, button, event):
        pass

    ### end DragTreeView ###


class PlaylistModel(gtk.GenericTreeModel):
    columns = ['tracknumber', 'title', 'album', 'artist']
    column_types = (str, str, str, str)

    def __init__(self, playlist):
        gtk.GenericTreeModel.__init__(self)
        self.playlist = playlist

        event.add_callback(self.on_tracks_added,
                "playlist_tracks_added", playlist)
        event.add_callback(self.on_tracks_removed,
                "playlist_tracks_removed", playlist)

    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY

    def on_get_n_columns(self):
        return len(self.columns)

    def on_get_column_type(self, index):
        return self.column_types[index]

    def on_get_iter(self, path):
        rowref = path[0]
        if rowref < len(self.playlist):
            return rowref
        else:
            return None

    def on_get_path(self, rowref):
        return (rowref,)

    def on_get_value(self, rowref, column):
        return self.playlist[rowref].get_tag_display(self.columns[column])

    def on_iter_next(self, rowref):
        rowref = rowref+1
        if rowref < len(self.playlist):
            return rowref
        else:
            return None

    def on_iter_children(self, parent):
        if rowref:
            return None
        try:
            return self.playlist[0]
        except IndexError:
            return None

    def on_iter_has_child(self, rowref):
        return False

    def on_iter_n_children(self, rowref):
        if rowref:
            return 0
        return len(self.playlist)

    def on_iter_nth_child(self, parent, n):
        if parent:
            return None
        try:
            return self.playlist[n]
        except IndexError:
            return None

    def on_iter_parent(self, child):
        return None


    def on_tracks_added(self, typ, playlist, tracktups):
        for idx, tr in tracktups:
            self.row_inserted((idx,), self.get_iter((idx,)))

    def on_tracks_removed(self, typ, playlist, tracktups):
        tracktups.reverse()
        for idx, tr in tracktups:
            self.row_deleted((idx,))

    def get_track(self, path):
        return self.playlist[path[0]]


class Playlist(object):
    """


        EVENTS:
            playlist_track_added
                fired: after tracks are added
                data: list of tuples of (index, track)
            playlist_track_removed
                fired: after tracks are removed
                data: list of tuples of (index, track)
    """
    def __init__(self, name, initial_tracks=[]):
        # MUST copy here, hence the :
        for tr in initial_tracks:
            if not isinstance(tr, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
        self.__tracks = list(initial_tracks)
        self.__random_mode = "disabled"
        self.__repeat_mode = "disabled"
        self.__dynamic_mode = "disabled"
        self.__dirty = False
        self.__name = name
        self.__tracks_history = collections.deque()
        self.__current_pos = -1

    ### playlist-specific API ###

    def _set_name(self, name):
        self.__name = name

    name = property(lambda self: self.__name, _set_name)
    dirty = property(lambda self: self.__dirty)

    def clear(self):
        del self[:]

    def get_current_pos(self):
        return self.__current_pos

    def set_current_pos(self, pos):
        self.__current_pos = pos
        event.log_event("playlist_current_pos_changed", self, pos)

    current_pos = property(get_current_pos, set_current_pos)

    def get_current(self):
        return self.__tracks[self.current_pos]

    current = property(get_current)

    def next(self):
        self.current_pos += 1
        return self.get_current()

    def prev(self):
        self.current_pos -= 1
        return self.get_current()

    def get_random_mode(self):
        return self.__random_mode

    def set_random_mode(self, mode):
        pass

    random_mode = property(get_random_mode, set_random_mode)

    def get_repeat_mode(self):
        return self.__repeat_mode

    def set_repeat_mode(self, mode):
        pass

    repeat_mode = property(get_repeat_mode, set_repeat_mode)

    def get_dynamic_mode(self):
        return self.__dynamic_mode

    def set_dynamic_mode(self, mode):
        pass

    dynamic_mode = property(get_dynamic_mode, set_dynamic_mode)

    def randomize(self):
        # TODO: add support for randomizing a subset of the list?
        trs = self[:]
        random.shuffle(trs)
        self[:] = trs


    # TODO[0.4?]: drop our custom disk playlist format in favor of an
    # extended XSPF playlist (using xml namespaces?).

    # TODO: add timeout saving support. 5-10 seconds after last change,
    # perhaps?

    def save_to_location(self, location):
        pass

    def load_from_location(self, location):
        pass

    ### view API ###

    # how views need to work:
    #   when the following methods are called, they do NOT affect the
    #   underlying order, only the 'apparent' order. HOWEVER, if the
    #   structure is modified when a view is in effect, the view
    #   replaces the current order.

    def reverse(self):
        # reverses current view
        pass

    def sort(self):
        # sorts current view
        pass

    # filter acts like a view method, EXCEPT that when it is active, it
    # is illegal to add or reorder items in the playlist. attempting to do
    # so will raise a <TODO>Exception. Deletion while a filter is active
    # is allowed, however items deleted must be visible under the
    # filter.
    # GUI should disable (grey out, beocme insensitive to DnD, etc.)
    # appropriate actions when these conditions are in effect.

    def filter(self):
        # filters the playlist. acts on current view if new filter is a
        # superset of the old one, and on the entire list if it is not.
        pass


    ### list-like API methods ###
    # parts of this section are taken from
    # http://code.activestate.com/recipes/440656-list-mixin/

    def __len__(self):
        return len(self.__tracks)

    def __contains__(self, track):
        return self.__tracks.__contains__(track)

    def __tuple_from_slice(self, i):
        """
            Get (start, end, step) tuple from slice object.
        """
        (start, end, step) = i.indices(len(self))
        # Replace (0, -1, 1) with (0, 0, 1) (misfeature in .indices()).
        #if step == 1:
        #    if end < start:
        #        end = start
        #        step = None
        if i.step == None:
            step = 1
        return (start, end, step)

    def __getitem__(self, i):
        return self.__tracks.__getitem__(i)

    def __setitem__(self, i, value):
        oldtracks = self.__getitem__(i)
        if isinstance(i, slice):
            for x in value:
                if not isinstance(x, trax.Track):
                    raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            (start, end, step) = self.__tuple_from_slice(i)
            if step != 1:
                if len(value) != len(oldtracks):
                    raise ValueError, "Extended slice assignment must match sizes."
                self.__tracks.__setitem__(i, value)
                event.log_event_sync('playlist_tracks_removed', self,
                        zip(range(start, end, step), oldtracks))
            else:
                self.__tracks.__setitem__(i, value)
                event.log_event_sync('playlist_tracks_removed', self,
                        zip(range(start, end, step), oldtracks))
                end = start + len(value)
            event.log_event_sync('playlist_tracks_added', self,
                    zip(range(start, end, step), value))
        else:
            if not isinstance(value, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks[i] = value
            event.log_event_sync('playlist_tracks_removed', self, [(i, oldtracks)])
            event.log_event_sync('playlist_tracks_added', self, [(i, value)])

    def __delitem__(self, i):
        if isinstance(i, slice):
            (start, end, step) = self.__tuple_from_slice(i)
        oldtracks = self.__getitem__(i)
        self.__tracks.__delitem__(i)

        if isinstance(i, slice):
            event.log_event_sync('playlist_tracks_removed', self,
                    zip(range(start, end, step), oldtracks))
        else:
            event.log_event_sync('playlist_tracks_removed', self,
                    [(i, oldtracks)])

    def append(self, other):
        self[len(self):len(self)] = [other]

    def extend(self, other):
        self[len(self):len(self)] = other

    def count(self, other):
        return self.__tracks.count(other)

    def index(self, item, start=0, end=None):
        if end is None:
            return self.__tracks.index(item, start)
        else:
            return self.__tracks.index(item, start, end)




