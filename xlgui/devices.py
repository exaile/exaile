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

import logging

from gi.repository import Gtk

from xl import event
from xlgui.guiutil import GtkTemplate

logger = logging.getLogger(__name__)


@GtkTemplate('ui', 'device_manager.ui')
class ManagerDialog(Gtk.Window):
    """
    the device manager dialog
    """

    __gtype_name__ = 'DeviceManager'

    tree_devices, model = GtkTemplate.Child.widgets(2)

    def __init__(self, parent, main):
        Gtk.Window.__init__(self)
        self.init_template()

        self.main = main
        self.device_manager = self.main.exaile.devices
        self.set_transient_for(parent)

        # GtkListStore self.model: first column (PyObject) should really be of
        # type devices.Device, but that doesn't work with GtkBuilder.

        self.populate_tree()
        event.add_ui_callback(self.populate_tree, 'device_added')
        event.add_ui_callback(self.populate_tree, 'device_removed')

    def populate_tree(self, *args):
        self.model.clear()
        for d in self.device_manager.get_devices():
            self.model.append([d, None, d.get_name(), d.__class__.__name__])

    def _get_selected_devices(self):
        sel = self.tree_devices.get_selection()
        (model, paths) = sel.get_selected_rows()
        devices = []
        for path in paths:
            iter = self.model.get_iter(path)
            device = self.model.get_value(iter, 0)
            devices.append(device)

        return devices

    @GtkTemplate.Callback
    def on_btn_connect_clicked(self, *args):
        devices = self._get_selected_devices()

        for d in devices:
            d.connect()

    @GtkTemplate.Callback
    def on_btn_disconnect_clicked(self, *args):
        devices = self._get_selected_devices()

        for d in devices:
            d.disconnect()

    @GtkTemplate.Callback
    def on_btn_close_clicked(self, *args):
        self.hide()
        self.destroy()

    def run(self):
        self.show_all()
