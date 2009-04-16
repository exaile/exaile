"""
    Queue manager dialog
"""

from xl import xdg
from xl.nls import gettext as _
from operator import itemgetter
from copy import copy
import xl.event
import os
import gtk
import gtk.glade
import logging

LOG = logging.getLogger('exaile.xlgui.queue')

class QueueManager(object):

    """
        GUI to manage a queue
    """

    def __init__(self, queue):
        self._queue = queue

        self._xml = gtk.glade.XML(
                xdg.get_data_path(os.path.join('glade', 'queue_dialog.glade')),
                    'QueueManagerDialog', 'exaile')
        self._xml.get_widget('remove_all_button').set_image(
               gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON))

        self._dialog = self._xml.get_widget('QueueManagerDialog')
        self._dialog.connect('destroy', self.destroy)
        self._xml.signal_autoconnect({
            'close_dialog': self.destroy,
            'on_top_button_clicked': self.selected_to_top,
            'on_up_button_clicked': self.selected_up,
            'on_remove_button_clicked': self.remove_selected,
            'on_down_button_clicked': self.selected_down,
            'on_bottom_button_clicked': self.selected_to_bottom,
            'on_remove_all_button_clicked': self.remove_all,
            })

        self.__setup_callbacks()

        self._model = gtk.ListStore(int, str, object)
        self._queue_view = self._xml.get_widget('queue_tree')
        self._queue_view.set_model(self._model)
        self.__last_tracks = []
        self.__populate_queue()
        self.__setup_queue()

    def __setup_callbacks(self):
        for callback in self.__callbacks():
            xl.event.add_callback(*callback)

    def __teardown_callbacks(self):
        for callback in self.__callbacks():
            xl.event.remove_callback(*callback)

    def __populate_queue_cb(self, *e):
        self.__populate_queue()

    def __callbacks(self):
        yield (self.__populate_queue_cb, 'playback_start')
        yield (self.__populate_queue_cb, 'tracks_added', self._queue)

    def __setup_queue(self):
        """Adds columns to _queue_view"""
        renderer = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('#'), renderer, text=0)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self._queue_view.append_column(col)

        renderer = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Title'), renderer, text=1)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self._queue_view.append_column(col)

    def __populate_queue(self):
        """Populates the _model with tracks"""
        tracks = self._queue.get_ordered_tracks()
        if tracks == self.__last_tracks:
            LOG.debug(_("Tracks did not change, no need to update"))
            return
        # Find the row that will be selected

        if self._queue_view is not None:
            model, iter = self._queue_view.get_selection().get_selected()
            if iter:
                target = model.get_value(iter, 2)
                try:
                    new_cursor_pos = tracks.index(target)
                except ValueError:
                    pass
        if 'new_cursor_pos' not in locals():
            new_cursor_pos = None
        self.__last_tracks = copy(tracks)
        self._model.clear()
        # Add the rows
        for i, track in zip(xrange(1, len(tracks) + 1), tracks):
            self._model.append((i, unicode(track), track))
        # Select new row
        if new_cursor_pos is not None and hasattr(self, '_queue_view'):
            self._queue_view.set_cursor((new_cursor_pos,))

    def show(self):
        """
            Displays this window
        """
        self._dialog.show_all()

    def destroy(self, *e):
        """
            Destroys this window
        """
        self._dialog.destroy()
        self.__teardown_callbacks()

# removing items
    def remove_selected(self, button, *userparams):
        model, iter = self._queue_view.get_selection().get_selected()
        if not iter:
            return
        i = model.get_value(iter, 0) - 1
        self.remove(i)

    def remove_all(self, button, *userparams):
        while len(self._queue.get_ordered_tracks()):
            self.remove(0)

    def remove(self, i):
        """Removes the ith item from the queue, 0-indexed"""
        cur_queue = self._queue.get_ordered_tracks()
        if i < 0 or i >= len(cur_queue):
            LOG.error(_("Gave an invalid number to remove"))
            return
        cur_queue.pop(i)
        self.__populate_queue()

# Moving callbacks
    def selected_to_top(self, button, *userparams):
        self.reorder(lambda x, l: 0)

    def selected_up(self, button, *userparams):
        self.reorder(lambda x, l: x - 1)

    def selected_down(self, button, *userparams):
        self.reorder(lambda x, l: x + 1)

    def selected_to_bottom(self, button, *userparams):
        self.reorder(lambda x, l: l - 1)

    def reorder(self, new_loc):
        """Reorders the tracks in the queue.

        new_loc is a function that takes two variables, x and l. x will be the
        the index of the currently selected item. l will be the size of the
        queue. The function need not bounds check.

        """
        model, iter = self._queue_view.get_selection().get_selected()
        if not iter:
            return
        
        i = model.get_value(iter, 0) - 1
        tracks = self._queue.get_ordered_tracks()
        if callable(new_loc):
            new_loc = new_loc(i, len(tracks))
        if new_loc < 0 or new_loc >= len(tracks):
            new_loc = i

        new_order = list(zip(range(len(tracks)), tracks))
        new_order[new_loc], new_order[i] = new_order[i], new_order[new_loc]

        self._queue.set_ordered_tracks(list(map(itemgetter(1), new_order)))
        self.__populate_queue()

def main():
    class Track(object):
        def __init__(self, title):
            self.tags = {'title': title}
        def __unicode__(self):
            return self.tags['title']
        def __str(self):
            return str(unicode(self))
    class Foo(object):
        ordered_tracks = [Track('Track Foo by bar on baz'), Track('bar')]
        get_ordered_tracks = lambda self: self.ordered_tracks
        def set_ordered_tracks(self, v):
            self.ordered_tracks = v
    dialog = QueueManager(Foo())
    dialog.show()
    try:
        gtk.main()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
