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
import gtk, gtk.glade
from xl import xdg, settings, event, devices
from xlgui import collection
import logging

logger = logging.getLogger(__name__)


class ManagerDialog(object):
    """
        the device manager dialog
    """

    def __init__(self, parent, main):
        self.main = main
        self.parent = parent
        self.device_manager = self.main.exaile.devices
        self.xml = gtk.glade.XML(
                xdg.get_data_path('glade/device_manager.glade'), 
                'device_manager', 'exaile')
        self.window = self.xml.get_widget('device_manager')
        self.window.set_transient_for(self.parent)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.connect('delete-event', self.on_close)

        self.xml.signal_autoconnect({
            'on_btn_connect_clicked': self.on_connect,
            'on_btn_disconnect_clicked': self.on_disconnect,
            'on_btn_edit_clicked': self.on_edit,
            'on_btn_add_clicked': self.on_add,
            'on_btn_remove_clicked': self.on_remove,
            'on_btn_close_clicked': self.on_close,
            })

        # TODO: make these actually work.  For now, they are hidden
        for item in ('add', 'edit', 'remove'):
            self.xml.get_widget('btn_%s' % item).destroy()

        # object should really be devices.Device, but it doesnt work :/
        self.model = gtk.ListStore(object, gtk.gdk.Pixbuf, str, str)
        self.tree = self.xml.get_widget('tree_devices')
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
