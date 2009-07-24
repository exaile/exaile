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

import gtk, gtk.glade, gobject
from xl import xdg

class Panel(gobject.GObject):
    """
        The base panel class.

        This class is abstract and should be subclassed.  All subclasses
        should define a 'gladeinfo' and 'name' variables.
    """
    gladeinfo = ('panel.glade', 'PanelWindow')

    def __init__(self, parent, name=None):
        """
            Intializes the panel
            
            @param controller: the main gui controller
        """
        gobject.GObject.__init__(self)
        self.name = name
        self.parent = parent

        # if the gladefile starts with file:// use the full path minus
        # file://, otherwise check in the data directories
        gladefile = self.gladeinfo[0]
        if not gladefile.startswith('file://'):
            gladefile = xdg.get_data_path('glade/%s' % gladefile)
        else:
            gladefile = gladefile[7:]

        self.xml = gtk.glade.XML(gladefile, self.gladeinfo[1], 'exaile')
        self._child = None

    def get_panel(self):
        if not self._child:
            window = self.xml.get_widget(self.gladeinfo[1])
            self._child = window.get_child()
            window.remove(self._child)
            if not self.name:
                self.name = window.get_title()
            window.destroy()

        return (self._child, self.name)

    def __del__(self):
        import xlgui
        try:
            xlgui.controller().remove_panel(self._child)
        except ValueError:
            pass


