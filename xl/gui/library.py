# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import gtk
from gettext import gettext as _
from xl import xlmisc

class LibraryDialog(object):
    """
        Allows you to choose which directories are in your library
    """
    def __init__(self, exaile):
        """
            Initializes the dialog
        """
        self.exaile = exaile
        self.xml = gtk.glade.XML('exaile.glade', 'LibraryManager', 'exaile')
        self.dialog = self.xml.get_widget('LibraryManager')
        self.list = xlmisc.ListBox(self.xml.get_widget('lm_list_box'))
        self.addList = []
        self.removeList = []
        self.dialog.set_transient_for(exaile.window)
        self.xml.get_widget('lm_add_button').connect('clicked',
            self.on_add)
        self.xml.get_widget('lm_remove_button').connect('clicked',
            self.on_remove)

        self.xml.get_widget('lm_cancel_button').connect('clicked',
            lambda e: self.dialog.response(gtk.RESPONSE_CANCEL))
        self.xml.get_widget('lm_apply_button').connect('clicked',
            self.on_apply)

        items = exaile.settings.get_list("search_paths", [])
        self.items = []
        for i in items:
            if i: self.items.append(i)

        if self.items:
            self.list.set_rows(self.items)

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
        return self.items

    def on_apply(self, widget):
        """
            Saves the paths in the dialog, and updates the library
        """
        self.exaile.settings['search_paths'] = self.list.rows
        self.exaile.settings['add_paths'] = self.addList
        self.exaile.settings['remove_paths'] = self.removeList
        self.dialog.response(gtk.RESPONSE_APPLY)

    def on_remove(self, widget):
        """
            removes a path from the list
        """
        item = self.list.get_selection()
        index = self.list.rows.index(item)
        self.removeList.append(item)
        self.list.remove(item)
        selection = self.list.list.get_selection()
        if index >= len(self.list.rows):
            selection.select_path(index - 1)
        else:
            selection.select_path(index)

    def on_add(self, widget):
        """
            Adds a path to the list
        """
        dialog = gtk.FileChooserDialog(_("Add a directory"),
            self.exaile.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_ADD, gtk.RESPONSE_OK))
        response = dialog.run()
        dialog.hide()
        if response == gtk.RESPONSE_OK:
            path = dialog.get_filename()
            if path in self.items:
                common.error(self.exaile.window, _('Path is already in '
                    'your collection.'))
                return

            for item in self.items:
                if path.startswith(item):
                    # our added path is a subdir of an existing path
                    common.error(self.exaile.window, _('Path is already '
                        'in your collection, or is a subdirectory of another '
                        'path in your collection'))
                    return
                elif item.startswith(path):
                    # our added path encompasses some previously added directories
                    log('LibraryManager: Newly added directory contains' 
                        'the directory %s, which will be removed from' 
                        'the list' % (item,))
                    self.items.remove(item)

            self.addList.append(path)
	    self.list.append(path)
        dialog.destroy()

