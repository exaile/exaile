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

from xlgui import panel
from xlgui.panel.collection import CollectionPanel

class DevicePanel(panel.Panel):
    """
        generic panel for devices
    """
    gladeinfo = ('device_panel.glade', 'DevicePanelWindow')

    def __init__(self, device, name=None):

        panel.Panel.__init__(self, name)
        self.device = device

        self.notebook = self.xml.get_widget("device_notebook")

        self.collectionpanel = CollectionPanel(self, 
                device.collection, name=self.name)

    def get_panel(self):
        return self.collectionpanel.get_panel()

    def add_panel(self, child, name):
        label = gtk.Label(name)
        self.notebook.append_page(child, label)

    def load_tree(self, *args):
        self.collectionpanel.load_tree(*args)
