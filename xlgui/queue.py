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

"""
    Queue manager dialog
"""
from copy import copy
import logging
from operator import itemgetter
import os

import gtk

import xl.event
from xl import xdg
from xl.nls import gettext as _
from xlgui import main, playlist

LOG = logging.getLogger('exaile.xlgui.queue')

class QueueManager(object):

    """
        GUI to manage a queue
    """

    def __init__(self, parent, queue):
        self._queue = queue

        self.builder = gtk.Builder()
        self.builder.add_from_file(
            xdg.get_data_path(os.path.join('ui', 'queue_dialog.ui')))

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
