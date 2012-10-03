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
import threading

import gtk

from xl.nls import gettext as _
from xl import xdg, settings, event, devices
from xlgui import collection

logger = logging.getLogger(__name__)




class ManagerDialog(object):
    """
        the device manager dialog
    """

    def __init__(self, parent, main):
        self.main = main
        self.parent = parent
        self.device_manager = self.main.exaile.devices
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/device_manager.ui'))
        self.window = self.builder.get_object('device_manager')
        self.window.set_transient_for(self.parent)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.connect('delete-event', self.on_close)

        self.builder.connect_signals({
            'on_btn_connect_clicked': self.on_connect,
            'on_btn_disconnect_clicked': self.on_disconnect,
            'on_btn_edit_clicked': self.on_edit,
            'on_btn_add_clicked': self.on_add,
            'on_btn_remove_clicked': self.on_remove,
            'on_btn_close_clicked': self.on_close,
            })

        # TODO: make these actually work.  For now, they are hidden
        for item in ('add', 'edit', 'remove'):
            self.builder.get_object('btn_%s' % item).destroy()

        # object should really be devices.Device, but it doesnt work :/
        self.model = gtk.ListStore(object, gtk.gdk.Pixbuf, str, str)
        self.tree = self.builder.get_object('tree_devices')
        self.tree.set_model(self.model)

        render = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn(_("Icon"), render)
        col.add_attribute(render, "pixbuf", 1)
        self.tree.append_column(col)

        render = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_("Device"), render)
        col.set_expand(True)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        col.add_attribute(render, "text", 2)
        self.tree.append_column(col)

        render = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_("Driver"), render)
        col.add_attribute(render, "text", 3)
        self.tree.append_column(col)

        self.populate_tree()
        event.add_callback(self.populate_tree, 'device_added')
        event.add_callback(self.populate_tree, 'device_removed')

    def populate_tree(self, *args):
        self.model.clear()
        for d in self.device_manager.list_devices():
            self.model.append([d, None, d.get_name(), d.__class__.__name__])

    def _get_selected_devices(self):
        sel = self.tree.get_selection()
        (model, paths) = sel.get_selected_rows()
        devices = []
        for path in paths:
            iter = self.model.get_iter(path)
            device = self.model.get_value(iter, 0)
            devices.append(device)

        return devices


    def on_connect(self, *args):
        devices = self._get_selected_devices()

        for d in devices:
            d.connect()

    def on_disconnect(self, *args):
        devices = self._get_selected_devices()

        for d in devices:
            d.disconnect()

    def on_edit(self, *args):
        logger.warning("NOT IMPLEMENTED")

    def on_add(self, *args):
        logger.warning("NOT IMPLEMENTED")

    def on_remove(self, *args):
        logger.warning("NOT IMPLEMENTED")

    def on_close(self, *args):
        self.window.hide()
        self.window.destroy()

    def run(self):
        self.window.show_all()
