# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
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

import gtk, gobject
from xlgui import panel, guiutil
from xl import xdg, event, common
import xl.radio
import threading
from gettext import gettext as _

class RadioPanel(panel.Panel):
    """
        The Radio Panel
    """
    gladeinfo = ('radio_panel.glade', 'RadioPanelWindow')

    def __init__(self, controller, radio_manager):
        """
            Initializes the radio panel
        """
        panel.Panel.__init__(self, controller)
        
        self.manager = radio_manager
        self.load_nodes = {}
        self.nodes = {}

        self._setup_tree()
        self._setup_widgets()
        self._connect_events()

        self.load_streams()

    def load_streams(self):
        """
            Loads radio streams from plugins
        """
        for name, value in self.manager.stations.iteritems():
            self.add_driver(value)

    def add_driver(self, driver):
        """
            Adds a driver to the radio panel
        """
        node = self.model.append(self.radio_root, [self.folder, driver])
        self.nodes[driver] = node
        self.load_nodes[driver] = self.model.append(node, 
            [self.refresh_image, _('Loading streams...')])
        self.tree.expand_row(self.model.get_path(self.radio_root), False)

    def _setup_widgets(self):
        """
            Sets up the various widgets required for this panel
        """
        pass

    def _connect_events(self):
        """
            Connects events used in this panel
        """
        self.tree.connect('row-expanded', self.on_row_expand)
        self.tree.connect('row-collapsed', self.on_collapsed)
        self.tree.connect('row-activated', self.on_row_activated)

        event.add_callback(lambda type, m, station:
            self.add_driver(station), 'station_added', self.manager)
        # TODO: handle removing of drivers

    def _setup_tree(self):
        """
            Sets up the tree that displays the radio panel
        """
        box = self.xml.get_widget('RadioPanel')
        self.tree = guiutil.DragTreeView(self)
        self.tree.set_headers_visible(False)

        # columns
        text = gtk.CellRendererText()
        icon = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn('radio')
        col.pack_start(icon, False)
        col.pack_start(text, True)
        col.set_attributes(icon, pixbuf=0)
        col.set_cell_data_func(text, self.cell_data_func)
        self.tree.append_column(col)

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, object)
        self.tree.set_model(self.model)

        self.open_folder = guiutil.get_icon('gnome-fs-directory-accept')
        self.track = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))
        self.folder = guiutil.get_icon('gnome-fs-directory')
        self.refresh_image = guiutil.get_icon('gtk-refresh')

        self.custom = self.model.append(None, [self.open_folder, _("Saved Stations")])
        self.radio_root = self.model.append(None, [self.open_folder, _("Radio "
            "Streams")])

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        box.pack_start(scroll, True, True)

    def on_row_activated(self, tree, path, column):
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 1)
        if isinstance(item, xl.radio.RadioItem):
            self.controller.main.add_playlist(item.get_playlist())

    def button_press(self, widget, event):
        """
            Called when someone clicks on the tree
        """
        pass

    def cell_data_func(self, column, cell, model, iter):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 1)
        cell.set_property('text', str(object))

    def drag_data_received(self, *e):
        pass

    def drag_get_data(self, *e):
        pass

    def on_row_expand(self, tree, iter, path):
        """
            Called when a user expands a row in the tree
        """
        driver = self.model.get_value(iter, 1)

        if isinstance(driver, xl.radio.RadioStation) or \
            isinstance(driver, xl.radio.RadioList):
            self._load_station(iter, driver)        

    @common.threaded 
    def _load_station(self, iter, driver):
        """
            Loads a radio station
        """

        if isinstance(driver, xl.radio.RadioStation):
            lists = driver.get_lists()
        else:
            lists = driver.get_items()

        gobject.idle_add(self._done_loading, iter, driver, lists, True)

    def _done_loading(self, iter, object, items, idle=False):
        """
            Called when an item is done loading.  Adds items to the tree
        """
        for item in items:
            if isinstance(item, xl.radio.RadioList): 
                node = self.model.append(self.nodes[object], [self.folder, item])
                self.nodes[item] = node
                self.load_nodes[item] = self.model.append(node,
                    [self.refresh_image, _("Loading streams...")]) 
            else:
                self.model.append(self.nodes[object], [self.track, item])

        self.model.remove(self.load_nodes[object])
        del self.load_nodes[object]

    def on_collapsed(self, tree, iter, path):
        """
            Called when someone collapses a tree item
        """
        self.model.set_value(iter, 0, self.folder)
