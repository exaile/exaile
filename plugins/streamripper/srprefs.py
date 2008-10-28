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

import os
from xlgui.prefs import widgets
from xl import xdg

name = 'Streamripper'
basedir = os.path.dirname(os.path.realpath(__file__))
glade = '%s/streamripper.glade' % basedir

class SavePreference(widgets.DirPrefsItem):
    default = os.getenv('HOME')
    name = 'plugin/streamripper/save_location'

class PortPreference(widgets.PrefsItem):
    default = '8888'
    name = 'plugin/streamripper/relay_port'
