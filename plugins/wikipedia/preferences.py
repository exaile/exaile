# Copyright (C) 2010 Guillaume Lecomte
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _('Wikipedia')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "data/preferences.ui")


class LocalePreference(widgets.Preference):
    default = 'en'
    name = 'plugin/wikipedia/language'
