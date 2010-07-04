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

import gtk

from xl import xdg, covers
from xl.nls import gettext as _
from xlgui import icons
from xlgui.preferences import widgets

name = _('Covers')
icon = 'image-x-generic'
ui = xdg.get_data_path('ui', 'preferences', 'cover.ui')

class TagCoverFetching(widgets.CheckPreference):
    default = True
    name = 'covers/use_tags'

class LocalCoverFetching(widgets.CheckPreference):
    default = True
    name = 'covers/use_localfile'

class CoverOrderPreference(widgets.OrderListPreference):
    """
        This little preference item shows kind of a complicated preference
        widget in action.  The defaults are dynamic.
    """
    name = 'covers/preferred_order'

    def __init__(self, preferences, widget):
        self.default = covers.MANAGER._get_methods()
        widgets.OrderListPreference.__init__(self, preferences, widget)

    def _set_value(self):
        self.model.clear()
        for item in self.default:
            self.model.append([item.name])

    def apply(self):
        if widgets.OrderListPreference.apply(self):
            covers.MANAGER.set_preferred_order(
                self._get_value())
        return True

class AutomaticCoverFetching(widgets.CheckPreference):
    default = True
    name = 'covers/automatic_fetching'
