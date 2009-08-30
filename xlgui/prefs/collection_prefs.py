# Copyright (C) 2009 Thomas E. Zander
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
from xlgui import commondialogs

name = _('Collection')
glade = xdg.get_data_path('glade/collection_prefs_pane.glade')

class CollectionStripArtistPreference(widgets.ListPrefsItem):
    default = "the"
    name = 'collection/strip_list'

    def _get_value(self):
        """
            Get the value, overrides the base class function
            because we don't need shlex parsing. We actually
            want values like "l'" here.
        """
        values = [v.lower() for v in self.widget.get_text().split(' ') if v is not '']
        return values

