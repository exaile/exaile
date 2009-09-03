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
from xl.nls import gettext as _

name = _('AudioScrobbler')
basedir = os.path.dirname(os.path.realpath(__file__))
glade = os.path.join(basedir, "asprefs_pane.glade")

class SubmitPreference(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/ascrobbler/submit'

class MenuCheck(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/ascrobbler/menu_check'

class UserPreference(widgets.PrefsItem):
    name = 'plugin/ascrobbler/user'

class PassPreference(widgets.HashedPrefsItem):
    name = 'plugin/ascrobbler/password'
    type = 'md5'

class UrlPreference(widgets.ComboEntryPrefsItem):
    name = 'plugin/ascrobbler/url'
    default = 'http://post.audioscrobbler.com/'
    preset_items = {
        'http://post.audioscrobbler.com/': _('Last.fm'),
        'http://turtle.libre.fm/': _('Libre.fm')
        }
