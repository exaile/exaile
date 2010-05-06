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
from xlgui.preferences import widgets
from xl import xdg
from xl.nls import gettext as _

name = _('AudioScrobbler')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "asprefs_pane.ui")

class SubmitPreference(widgets.CheckPreference):
    default = True
    name = 'plugin/ascrobbler/submit'

class MenuCheck(widgets.CheckPreference):
    default = False
    name = 'plugin/ascrobbler/menu_check'

class UserPreference(widgets.Preference):
    name = 'plugin/ascrobbler/user'

class PassPreference(widgets.HashedPreference):
    name = 'plugin/ascrobbler/password'

class UrlPreference(widgets.ComboEntryPreference):
    name = 'plugin/ascrobbler/url'
    default = 'http://post.audioscrobbler.com/'
    preset_items = {
        'http://post.audioscrobbler.com/': 'Last.fm',
        'http://turtle.libre.fm/': 'Libre.fm'
        }
