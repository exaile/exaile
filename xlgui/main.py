# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gtk, gtk.glade, gobject
from xl import xdg

class MainWindow(object):
    """
        Main Exaile Window
    """
    def __init__(self, controller):
        """
            Initializes the main window

            @param controller: the main gui controller
        """
        self.controller = controller

        self.xml = gtk.glade.XML('%smain.glade' % xdg.get_glade_dir(),
            'ExaileWindow', 'exaile')
        self.window = self.xml.get_widget('ExaileWindow')
        self.panel_notebook = self.xml.get_widget('panel_notebook')

        self.window.show_all()

    def add_panel(self, child, name):
        """
            Adds a panel to the panel notebook
        """
        label = gtk.Label(name)
        label.set_angle(90)
        self.panel_notebook.append_page(child, label)
