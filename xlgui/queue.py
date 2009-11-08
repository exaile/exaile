"""
    Queue manager dialog
"""

from xl import xdg
from xl.nls import gettext as _
from xlgui import main, playlist
from operator import itemgetter
from copy import copy
import xl.event
import os
import gtk
import logging

LOG = logging.getLogger('exaile.xlgui.queue')

class QueueManager(object):

    """
        GUI to manage a queue
    """

    def __init__(self, parent, queue):
        self._queue = queue

        self.builder = gtk.Builder()
        self.builder.add_from_file(
            xdg.get_data_path(os.path.join('ui', 'queue_dialog.glade')))

        self._dialog = self.builder.get_object('QueueManagerDialog')
        self._dialog.set_transient_for(parent)
        self._dialog.connect('delete-event', self.destroy)
        self.builder.connect_signals({
            'close_dialog': self.destroy,
            'on_remove_all_button_clicked': self.remove_all,
            })

        self._playlist = playlist.Playlist(main.mainwindow(),
            queue, queue, _column_ids=['tracknumber', 'title', 'artist'],
            _is_queue=True)
        self._playlist.scroll.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        box = self.builder.get_object('queue_box')
        box.pack_start(self._playlist)

    def show(self):
        """
            Displays this window
        """
        self._dialog.show_all()

    def run(self):
        return self._dialog.run()

    def destroy(self, *e):
        """
            Destroys this window
        """
        main.mainwindow().queue_playlist_draw()
        self._dialog.hide()

    def remove_all(self, button, *userparams):
        self._queue.clear()
