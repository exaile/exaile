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
import gtk
import gobject

from xlgui import panel
from xlgui.panel.collection import CollectionPanel

class ReceptiveCollectionPanel(CollectionPanel):
    def drag_data_received(self, widget, context, x, y, data, info, stamp):
        """
            stubb
        """
        uris = data.get_uris()
        tracks, playlists = self.tree.get_drag_data(uris)
        tracks = [ t for t in tracks if not \
                self.collection.loc_is_member(t.get_loc()) ]
        locs = [ t['__loc'] for t in tracks ]

        # FIXME:
        lib = self.collection.get_libraries()[0]

        # this _needs_ to be asynchronous
        for l in locs:
            lib.add(l)

class DevicePanel(panel.Panel):
    """
        generic panel for devices
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'collection-tree-loaded': (gobject.SIGNAL_RUN_LAST, None, ()),
    }

    gladeinfo = ('device_panel.glade', 'DevicePanelWindow')

    def __init__(self, parent, main, 
        device, name=None):

        panel.Panel.__init__(self, name)
        self.device = device

        self.notebook = self.xml.get_widget("device_notebook")

        self.collectionpanel = ReceptiveCollectionPanel(parent,
            collection=device.collection, name=name)

        self.collectionpanel.connect('append-items',
            lambda *e: self.emit('append-items', *e[1:]))
        self.collectionpanel.connect('queue-items',
            lambda *e: self.emit('queue-items', *e[1:]))
        self.collectionpanel.connect('collection-tree-loaded',
            lambda *e: self.emit('collection-tree-loaded'))

    def get_panel(self):
        return self.collectionpanel.get_panel()

    def add_panel(self, child, name):
        label = gtk.Label(name)
        self.notebook.append_page(child, label)

    def load_tree(self, *args):
        self.collectionpanel.load_tree(*args)
