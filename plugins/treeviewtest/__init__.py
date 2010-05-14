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

import gtk, gobject
import collections
import os
from xl.nls import gettext as _
from xl import event, common, trax

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
        self.window = gtk.Window()
        self.swindow = gtk.ScrolledWindow()
        self.tview = gtk.TreeView()
        self.model = PlaylistModel(pl)

        for idx, col in enumerate(self.model.columns):
            cell = gtk.CellRendererText()
            tvcol = gtk.TreeViewColumn(col, cell, text=idx)
            self.tview.append_column(tvcol)


        self.window.add(self.swindow)
        self.swindow.add(self.tview)
        self.tview.set_model(self.model)
        self.window.show_all()

    def destroy(self):
        self.window.destroy()



class PlaylistModel(gtk.GenericTreeModel):
    columns = ['tracknumber', 'title', 'album', 'artist']
    column_types = (str, str, str, str)

    def __init__(self, playlist):
        gtk.GenericTreeModel.__init__(self)
        self.playlist = playlist

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
        self[:] = []

    def get_current_pos(self):
        return self.__current_pos

    def set_current_pos(self, pos):
        pass

    current_pos = property(get_current_pos, set_current_pos)

    def get_current(self):
        return self.__tracks[self.current_pos]

    current = property(get_current)

    def next(self):
        pass

    def prev(self):
        pass

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
        if step == 1:
            if end < start:
                end = start
                step = None
        if i.step == None:
            step = None
        return (start, end, step)

    def __getitem__(self, i):
        return self.__tracks.__getitem__(i)

    def __setitem__(self, i, value):
        oldtracks = self.__getitem__(i)
        if isinstance(i, slice):
            for x in value:
                if not isinstance(x, trax.Track):
                    raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks.__setitem__(i, value)

            (start, end, step) = self.__tuple_from_slice(i)
            event.log_event_sync('playlist_tracks_removed', self,
                    zip(range(start, end, stop), oldtracks))
            event.log_event_sync('playlist_tracks_added', self,
                    zip(range(start, end, stop), value))
        else:
            if not isinstance(value, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks[i] = value
            event.log_event_sync('playlist_tracks_removed', self, [(i, oldtracks)])
            event.log_event_sync('playlist_tracks_added', self, [(i, value)])

    def __delitem__(self, i):
        oldtracks = self.__getitem__(i)
        self.__tracks.__delitem__(i)

        if ininstance(i, slice):
            (start, end, step) = self.__tuple_from_slice(i)
            event.log_event_sync('playlist_tracks_removed', self,
                    zip(range(start, end, step)), oldtracks)
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




