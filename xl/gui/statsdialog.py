# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import gtk
from xl impot xlmisc, common, library

class StatsDialog(gtk.Dialog):
    """
        Shows various statistics for the Exaile music library
    """
    def __init__(self, parent, exaile):
        """
            Initializes the dialog
        """
        self.set_title(_('Library Statistics'))

        self.main = gtk.VBox()
        self.main.set_border_width(5)

        self.child.add(main)
