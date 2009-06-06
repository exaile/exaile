# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 2, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

from xl.nls import gettext as _
import logging, os, threading
import gtk
from xl import event, xdg, collection
from xlgui import commondialogs

logger = logging.getLogger(__name__)

class CollectionScanThread(threading.Thread):
    """
        Scans the collection
    """
    def __init__(self, main, collection):
        """
            Initializes the thread
        
            @param colleciton: the collection to scan
        """
        threading.Thread.__init__(self)
        self.setDaemon(True)
    
        self.main = main
        self.collection = collection
        self.stopped = False

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
        self.main.collection_panel.load_tree()

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
        self.xml = gtk.glade.XML(xdg.get_data_path('glade/collection_manager.glade'), 
            'CollectionManager', 'exaile')
        self.dialog = self.xml.get_widget('CollectionManager')
        self.list = commondialogs.ListBox(self.xml.get_widget('lm_list_box'))
        self.add_list = []
        self.remove_list = []
        self.dialog.set_transient_for(self.parent)

        self.xml.signal_autoconnect({
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
        dialog = gtk.FileChooserDialog(_("Add a directory"),
            self.parent, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_ADD, gtk.RESPONSE_OK))
        dialog.set_current_folder(xdg.get_last_dir())
        response = dialog.run()
        dialog.hide()

        if response == gtk.RESPONSE_OK:
            path = dialog.get_filename()
            tmp_items = self.get_items()

            # Append os.sep so /ab is not detected as descendant of /a.
            sep = os.sep
            if path.endswith(sep):
                path_sep = path
            else:
                path_sep = path + sep

            # TODO: Copy the code from 0.2 to handle the opposite, e.g. adding
            # /a after /a/b should add /a and remove /a/b.

            for item in tmp_items:
                if not item: continue
                if item.endswith(sep):
                    item_sep = item
                else:
                    item_sep = item + sep
                if (path_sep.startswith(item_sep)):
                    # our added path is a subdir of an existing path
                    commondialogs.error(self.parent, _('Path is already '
                        'in your collection, or is a subdirectory of '
                        'another path in your collection'))
                    return
    
            self.list.append(path)

        dialog.destroy()
