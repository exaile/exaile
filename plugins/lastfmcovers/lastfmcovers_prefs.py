# Copyright (C) 2009 Aren Olson, Johannes Schwarz
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

import os

from xlgui.prefs import widgets
from xl.nls import gettext as _

name = _("Last.fm Covers")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "lastfmcovers_prefs_pane.ui")


class OverlayDisplay(widgets.ComboPrefsItem):
    default = 'extralarge'
    name = 'plugin/cover/overlay'
    map = ['small', 'medium', 'large', 'extralarge']
    def __init__(self, prefs, widget):
        widgets.ComboPrefsItem.__init__(self, prefs, widget, use_map=True)
