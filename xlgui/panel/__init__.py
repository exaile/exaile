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

import os

from gi.repository import Gtk
from gi.repository import GObject

from xl import xdg
from xlgui.widgets.notebook import NotebookPage
import logging


LOGGER = logging.getLogger(__name__)


class Panel(GObject.GObject):
    """
    The base panel class.

    This class is abstract and should be subclassed.  All subclasses
    should define a 'ui_info' and 'name' variables.
    """

    ui_info = ('panel.ui', 'PanelWindow')

    def __init__(self, parent, name, label=None):
        """
        Intializes the panel

        @param parent: the main window
        @type parent: Gtk.Window
        @param name: the name of the panel. should be unique.
        @param label: text of the label displayed to the user
        """
        GObject.GObject.__init__(self)
        self.name = name  # panel id
        self.label = label  # label to be displayed
        self.parent = parent

        # if the UI designer file starts with file:// use the full path minus
        # file://, otherwise check in the data directories
        ui_file = self.ui_info[0]
        if not os.path.isabs(ui_file):
            ui_file = xdg.get_data_path('ui', 'panel', ui_file)

        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_file)
        self._child = None

    def focus(self):
        """
        Makes this panel grab the keyboard focus
        Subclasses can override this to give focus to a particular widget
        or perform another action.
        """
        self._child.grab_focus()

    def get_panel(self):
        """
        Returns a NotebookPage object that will be used as the panel

        :returns: NotebookPage object
        """
        if not self._child:
            widget = self.builder.get_object(self.ui_info[1])
            if isinstance(widget, Gtk.Window):
                # the old way, for pre 4.0.0-compatibility
                child = widget.get_child()
                if not self.label:
                    self.label = widget.get_title()
                LOGGER.info(
                    "Old style panel %s is creating unnecessary Gtk.Window.", self.label
                )
                widget.remove(child)
                widget.destroy()
            else:
                child = widget

            self._child = NotebookPage(child, self.label, 'panel-tab-context')

        return self._child
