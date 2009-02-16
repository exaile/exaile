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

import gtk, gtk.glade, gobject
from xl import xdg

class Panel(object):
    """
        The base panel class.

        This class is abstract and should be subclassed.  All subclasses
        should define a 'gladeinfo' and 'name' variables.
    """
    gladeinfo = ('panel.glade', 'PanelWindow')

    def __init__(self, controller, name=None):
        """
            Intializes the panel
            
            @param controller: the main gui controller
        """
        self.controller = controller

        self.xml = gtk.glade.XML(xdg.get_data_path("glade/%s" %
            self.gladeinfo[0]), self.gladeinfo[1], 'exaile')

        window = self.xml.get_widget(self.gladeinfo[1])
        self._child = window.get_child()
        window.remove(self._child)

        if name == None:
            name = window.get_title()
        self.controller.add_panel(self._child, name)
        window.destroy()


    def __del__(self):
        try:
            self.controller.remove_panel(self._child)
        except ValueError:
            pass


