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

from xlgui.prefs import widgets
from xl import xdg
from xl.nls import gettext as _

name = _('Covers')
glade = xdg.get_data_path('glade/cover_prefs_pane.glade')

class CoverOrderPreference(widgets.OrderListPrefsItem):
    """
        This little preference item shows kind of a complicated preference
        widget in action.  The defaults are dynamic.
    """
    name = 'covers/preferred_order'

    def __init__(self, prefs, widget):
        self.default = prefs.main.exaile.covers.get_methods()
        widgets.OrderListPrefsItem.__init__(self, prefs, widget)

    def _set_value(self):
        self.model.clear()
        for item in self.default:
            self.model.append([item.name])

    def apply(self):
        if widgets.OrderListPrefsItem.apply(self):
            self.prefs.main.exaile.covers.set_preferred_order(
                self.items)
        return True
