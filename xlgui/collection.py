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
import os
import threading

import gio
import gobject
import gtk

from xl.nls import gettext as _
from xl import event, xdg, collection
from xlgui import commondialogs

logger = logging.getLogger(__name__)

class CollectionScanThread(threading.Thread):
    """
        Scans the collection
    """
    def __init__(self, main, collection, panel):
        """
            Initializes the thread

            @param colleciton: the collection to scan
        """
        threading.Thread.__init__(self)
        self.setDaemon(True)

        self.collection = collection
        self.main = main
        self.stopped = False
        self.panel = panel

    def stop_thread(self):
        """
            Stops the thread
        """
        self.collection.stop_scan()

    def progress_update(self, type, collection, progress):
        event.log_event('progress_update', self, progress)

    def thread_complete(self):
        """
            Called when the thread has finished normally
        """
        gobject.idle_add(self.panel.load_tree)

    def run(self):
        """
            Runs the thread
        """
        event.add_callback(self.progress_update, 'scan_progress_update',
            self.collection)

        self.collection.rescan_libraries()

        event.remove_callback(self.progress_update, 'scan_progress_update',
            self.collection)

class CollectionManagerDialog(object):
    """
        Allows you to choose which directories are in your library
    """
    def __init__(self, parent, main, collection):
        """
            Initializes the dialog
        """
        self.parent = parent
        self.main = main
        self.collection = collection
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/collection_manager.ui'))
        self.dialog = self.builder.get_object('CollectionManager')
        self.list = commondialogs.ListBox(self.builder.get_object('lm_list_box'))
        self.add_list = []
        self.remove_list = []
        self.dialog.set_transient_for(self.parent)

        self.builder.connect_signals({
            'on_add_button_clicked': self.on_add,
            'on_remove_button_clicked': self.on_remove
        })

        items = collection.libraries.keys()
        self.list.set_rows(items)

    def run(self):
        """
            Runs the dialog, waiting for a response before any other gui
            events occur
        """
        return self.dialog.run()

    def get_response(self):
        """
            Gets the response id
        """
        return self.dialog.get_response()

    def destroy(self):
        """
            Destroys the dialog
        """
        self.dialog.destroy()

    def get_items(self):
        """
            Returns the items in the dialog
        """
        return self.list.rows

    def on_remove(self, widget):
        """
            removes a path from the list
        """
        item = self.list.get_selection()
        if item is None:
            return

        index = self.list.rows.index(item)
        self.list.remove(item)
        selection = self.list.list.get_selection()
        if index > len(self.list.rows):
            selection.select_path(index - 1)
        else:
            selection.select_path(index)

    def on_add(self, widget):
        """
            Adds a path to the list
        """
        dialog = gtk.FileChooserDialog(_("Add a Directory"),
            self.parent, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_ADD, gtk.RESPONSE_OK))
        dialog.set_current_folder(xdg.get_last_dir())
        dialog.set_local_only(False) # enable gio
        response = dialog.run()
        dialog.hide()

        if response == gtk.RESPONSE_OK:
            gloc = gio.File(dialog.get_uri())
            items = [ (gio.File(i), i) for i in self.get_items() ]

            removes = []
            for gitem, item in items:
                if gloc.has_prefix(gitem):
                    commondialogs.error(self.parent,
                        _('Path is already in your collection, or is a '
                        'subdirectory of another path in your collection'))
                    break
                elif gitem.has_prefix(gloc):
                    removes.append(item)
            else:
                self.list.append(gloc.get_uri())
                for item in removes:
                    try:
                        self.list.remove(item)
                    except:
                        pass
        dialog.destroy()
