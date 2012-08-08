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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import os

import gtk
import gobject

from xl import xdg

class Panel(gobject.GObject):
    """
        The base panel class.

        This class is abstract and should be subclassed.  All subclasses
        should define a 'ui_info' and 'name' variables.
    """
    ui_info = ('panel.ui', 'PanelWindow')

    def __init__(self, parent, name=None):
        """
            Intializes the panel

            @param controller: the main gui controller
        """
        gobject.GObject.__init__(self)
        self.name = name
        self.parent = parent

        # if the UI designer file starts with file:// use the full path minus
        # file://, otherwise check in the data directories
        ui_file = self.ui_info[0]
        if not os.path.isabs(ui_file):
            ui_file = xdg.get_data_path('ui', 'panel', ui_file)

        self.builder = gtk.Builder()
        self.builder.add_from_file(ui_file)
        self._child = None

    def get_panel(self):
        if not self._child:
            window = self.builder.get_object(self.ui_info[1])
            self._child = window.get_child()
            window.remove(self._child)
            if not self.name:
                self.name = window.get_title()
            window.destroy()

        return (self._child, self.name)

    def __del__(self):
        import xlgui
        try:
            xlgui.get_controller().remove_panel(self._child)
        except ValueError:
            pass


