"""
    Queue manager dialog
"""

from future_builtins import map, zip

from xl import xdg
from xl.nls import gettext as _
from operator import itemgetter
import os
import gtk
import gtk.glade

class QueueManager(object):

    """
        GUI to manage a queue
    """

    def __init__(self, queue):
        self._queue = queue

        self._xml = gtk.glade.XML(
                xdg.get_data_path(os.path.join('glade', 'queue_dialog.glade')),
                    'QueueManagerDialog', 'exaile')

        self._dialog = self._xml.get_widget('QueueManagerDialog')
        self._xml.signal_autoconnect({
            'on_ok_button_clicked': self.destroy,
            'on_top_button_clicked': self.selected_to_top,
            'on_up_button_clicked': self.selected_up,
            'on_down_button_clicked': self.selected_down,
            'on_bottom_button_clicked': self.selected_to_bottom,
            })

        self._model = gtk.ListStore(int, str)
        self.__last_tracks = None
        self.__populate_queue()

        self._queue_view = self._xml.get_widget('queue_tree')
        self.__setup_queue()
        self._queue_view.set_model(self._model)

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
            return
        else:
            self.__last_tracks = tracks
        self._model.clear()
        for i, track in zip(xrange(1, len(tracks) + 1), tracks):
            self._model.append((i, unicode(track)))

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

# Moving callbacks
    def selected_to_top(self, button, *userparams):
        self.reorder(lambda x, l: 0)

    def selected_up(self, button, *userparams):
        self.reorder(lambda x, l: x-1)

    def selected_down(self, button, *userparams):
        self.reorder(lambda x, l: x+1)

    def selected_to_bottom(self, button, *userparams):
        self.reorder(lambda x, l: len(l) - 1)

    def reorder(self, new_loc):
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

        model.rows_reordered(None, None, list(map(itemgetter(0), new_order)))
        self._queue_view.set_cursor((new_order[i][0],))


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
