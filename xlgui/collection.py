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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

import gio
import gobject
import gtk
import logging
import os

from xl.nls import gettext as _
from xl import (
    collection,
    xdg
)
from xlgui.widgets import dialogs

logger = logging.getLogger(__name__)

class CollectionManagerDialog(object):
    """
        Allows you to choose which directories are in your library
    """
    def __init__(self, parent, collection):
        """
            Initializes the dialog
        """
        self.parent = parent
        self.collection = collection
        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path(
            'ui', 'collection_manager.ui'))
        self.dialog = builder.get_object('CollectionManager')
        self.dialog.set_transient_for(self.parent)
        self.view = builder.get_object('view')
        self.model = builder.get_object('model')
        self.remove_button = builder.get_object('remove_button')
        self.message = dialogs.MessageBar(
            parent=builder.get_object('content_area'),
            buttons=gtk.BUTTONS_CLOSE
        )

        builder.connect_signals(self)

        selection = self.view.get_selection()
        selection.connect('changed', self.on_selection_changed)

        for location, library in collection.libraries.iteritems():
            self.model.append([location, library.monitored])

    def run(self):
        """
            Runs the dialog, waiting for a response before any other gui
            events occur
        """
        return self.dialog.run()

    def hide(self):
        """
            Hides the dialog
        """
        self.dialog.hide()

    def destroy(self):
        """
            Destroys the dialog
        """
        self.dialog.destroy()

    def get_items(self):
        """
            Returns the items in the dialog
        """
        items = []

        for row in self.model:
            items += [(row[0], row[1])]

        return items

    def on_monitored_cellrenderer_toggled(self, cell, path):
        """
            Enables or disables monitoring
        """
        monitored = not cell.get_active()
        cell.set_active(monitored)
        self.model[path][1] = monitored

    def on_add_button_clicked(self, widget):
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
            location = gio.File(dialog.get_uri())
            removals = []

            for row in self.model:
                library_location = gio.File(row[0])
                monitored = row[1]

                if location.has_prefix(library_location):
                    self.message.show_warning(
                        _('Directory not added.'),
                        _('The directory is already in your collection '
                          'or is a subdirectory of another directory in '
                          'your collection.')
                    )
                    break
                elif library_location.has_prefix(location):
                    removals += [row.iter]
            else:
                self.model.append([location.get_uri(), False])

                for iter in removals:
                    self.model.remove(iter)

        dialog.destroy()

    def on_remove_button_clicked(self, widget):
        """
            removes a path from the list
        """
        selection = self.view.get_selection()
        model, iter = selection.get_selected()
        model.remove(iter)
    
    def on_selection_changed(self, selection):
        """
            Enables or disables the "Remove" button
        """
        rows_selected = selection.count_selected_rows() > 0
        self.remove_button.set_sensitive(rows_selected)

