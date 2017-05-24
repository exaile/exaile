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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _('Streamripper')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'streamripper.ui')


class SavePreference(widgets.DirPreference):
    default = os.getenv('HOME')
    name = 'plugin/streamripper/save_location'


class PortPreference(widgets.Preference):
    default = '8888'
    name = 'plugin/streamripper/relay_port'


class FilePreference(widgets.CheckPreference):
    default = False
    name = 'plugin/streamripper/single_file'


class DeletePreference(widgets.CheckPreference):
    default = True
    name = 'plugin/streamripper/delete_incomplete'
