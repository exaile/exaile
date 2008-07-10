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

import gtk
from xlgui import panel, guiutil, xdg

class FilesPanel(panel.Panel):
    """
        The Files panel
    """

    gladeinfo = ('files_panel.glade', 'FilesPanelWindow')

    def __init__(self, controller):
        """
            Initializes the files panel
        """
        panel.Panel.__init__(self, controller)

        self.box = self.xml.get_widget('files_box')

        self.targets = [('text/uri-list', 0, 0)]
        
        self.tree = guiutil.DragTreeView(self, True, True)
        self.tree.set_headers_visible(False)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(self.scroll, True, True)
        self.box.show_all()

    def drag_data_received(self, *e):
        """ 
            stub
        """
        pass

    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def drag_get_data(self, *e):
        """ 
            stub
        """
        pass
