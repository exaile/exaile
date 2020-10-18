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

from gi.repository import Gio
from gi.repository import Gtk
import logging

import xl.collection
from xl.nls import gettext as _
from xl import xdg
from xlgui.widgets import dialogs
from xlgui.guiutil import GtkTemplate

logger = logging.getLogger(__name__)


@GtkTemplate('ui', 'collection_manager.ui')
class CollectionManagerDialog(Gtk.Dialog):
    """
    Allows you to choose which directories are in your library
    """

    __gtype_name__ = 'CollectionManager'

    view, model, remove_button, content_area = GtkTemplate.Child.widgets(4)
    location_column, location_cellrenderer = GtkTemplate.Child.widgets(2)

    def __init__(self, parent, collection: xl.collection.Collection):
        """
        Initializes the dialog
        """
        Gtk.Dialog.__init__(self)
        self.init_template()

        self.parent = parent
        self.collection = collection

        self.set_transient_for(self.parent)
        self.message = dialogs.MessageBar(
            parent=self.content_area, buttons=Gtk.ButtonsType.CLOSE
        )

        for location, library in collection.libraries.items():
            self.model.append([location, library.monitored, library.startup_scan])

        # Override the data function for location_column, so that it
        # displays parsed location names instead of escaped URIs
        def display_parsed_location(column, cell, model, iter, *data):
            location_uri = model.get(iter, 0)[0]  # first column
            location = Gio.File.new_for_uri(location_uri)
            cell.set_property("text", location.get_parse_name())

        self.location_column.set_cell_data_func(
            self.location_cellrenderer, display_parsed_location
        )

    def get_items(self):
        """
        Returns the items in the dialog
        """
        items = []

        for row in self.model:
            items += [(row[0], row[1], row[2])]

        return items

    @GtkTemplate.Callback
    def on_monitored_cellrenderer_toggled(self, cell, path):
        """
        Enables or disables monitoring
        """
        monitored = not cell.get_active()
        cell.set_active(monitored)
        self.model[path][1] = monitored

    @GtkTemplate.Callback
    def on_startup_cellrenderer_toggled(self, cell, path):
        """
        Enables or disables scanning on startup
        """
        if self.model[path][1]:
            scan_on_startup = not cell.get_active()
            cell.set_active(scan_on_startup)
            self.model[path][2] = scan_on_startup

    @GtkTemplate.Callback
    def on_add_button_clicked(self, widget):
        """
        Adds a path to the list
        """
        dialog = Gtk.FileChooserDialog(
            _("Add a Directory"),
            self.parent,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_ADD,
                Gtk.ResponseType.OK,
            ),
        )
        dialog.set_current_folder(xdg.get_last_dir())
        dialog.set_local_only(False)  # enable gio
        response = dialog.run()

        # XXX: For some reason, on Ubuntu 12.10 (GTK 2.24.13), hiding the
        # dialog before retrieving the results causes an incorrect URI
        # to be retrieved.

        uri = dialog.get_uri()
        dialog.hide()

        if response == Gtk.ResponseType.OK:
            location = Gio.File.new_for_uri(uri)
            removals = []

            for row in self.model:
                library_location = Gio.File.new_for_uri(row[0])
                # monitored = row[1]
                # scan_on_startup = row[2]

                if location.equal(library_location) or location.has_prefix(
                    library_location
                ):
                    self.message.show_warning(
                        _('Directory not added.'),
                        _(
                            'The directory is already in your collection '
                            'or is a subdirectory of another directory in '
                            'your collection.'
                        ),
                    )
                    break
                elif library_location.has_prefix(location):
                    removals += [row.iter]
            else:
                self.model.append([location.get_uri(), False, False])

                for iter in removals:
                    self.model.remove(iter)

        dialog.destroy()

    @GtkTemplate.Callback
    def on_remove_button_clicked(self, widget):
        """
        removes a path from the list
        """
        selection = self.view.get_selection()
        model, iter = selection.get_selected()
        model.remove(iter)

    @GtkTemplate.Callback
    def on_rescan_button_clicked(self, widget):
        """
        Triggers rescanning the collection
        """

        from xlgui import main

        main.mainwindow().controller.on_rescan_collection()

    @GtkTemplate.Callback
    def on_force_rescan_button_clicked(self, widget):
        """
        Triggers a slow rescan of the collection
        """

        from xlgui import main

        main.mainwindow().controller.on_rescan_collection_forced()

    @GtkTemplate.Callback
    def on_selection_changed(self, selection):
        """
        Enables or disables the "Remove" button
        """
        rows_selected = selection.count_selected_rows() > 0
        self.remove_button.set_sensitive(rows_selected)
