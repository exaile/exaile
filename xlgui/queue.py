"""
    Queue manager dialog
"""

from future_builtins import map, zip

from xl import xdg
from xl.nls import gettext as _
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
            })

        self._model = gtk.ListStore(int, str)
        self.__last_tracks = None
        self.__populate_queue()

        self._queue_view = self._xml.get_widget('queue_tree')
        self._queue_view.set_model(self._model)
        self._selection = self._queue_view.get_selection()
        self.__setup_queue()

    def __setup_queue(self):
        """Adds columns to _queue_view"""
        text = gtk.CellRendererText()

        col = gtk.TreeViewColumn(_('#'), text, text=0)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self._queue_view.append_column(col)

        col = gtk.TreeViewColumn(_('Title'), text, text=0)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self._queue_view.append_column(col)

    def __populate_queue(self):
        """Populates the _model with tracks"""
        tracks = self._queue.ordered_tracks()
        if tracks == self.__last_tracks:
            return
        else:
            self.__last_tracks = tracks
        #TODO Clear column
        set(map(self._model.append,
                ((i, unicode(track)) for i, track in
                                zip(xrange(1, len(tracks)+1), tracks))
                )
           )

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

def main():
    class Track(object):
        def __init__(self, title):
            self.tags = {'title': title}
        def __unicode__(self):
            return self.tags['title']
        def __str(self):
            return str(unicode(self))
    class Foo(object):
        ordered_tracks=lambda self: [Track('foo')]
    dialog = QueueManager(Foo())
    dialog.show()
    try:
        gtk.main()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
