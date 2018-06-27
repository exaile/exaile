# Copyright (C) 2010 Brian Parma
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
from xlgui import icons
from xl.nls import gettext as _

name = _('Multi-Alarm Clock')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "malrmclk.ui")

icons.MANAGER.add_icon_name_from_directory('clock', os.path.join(basedir, 'icons'))
icon = 'clock'


class FadingEnabledPreference(widgets.CheckPreference):
    name = 'plugin/multialarmclock/fading_on'
    default = True


class FadingConditional(widgets.CheckConditional):
    condition_preference_name = 'plugin/multialarmclock/fading_on'


class RestartPlaylistPreference(widgets.CheckPreference):
    name = 'plugin/multialarmclock/restart_playlist_on'
    default = False


class FadeMinVolumePreference(widgets.SpinPreference, FadingConditional):
    name = 'plugin/multialarmclock/fade_min_volume'
    default = 0

    def __init__(self, prefs, widget):
        widgets.SpinPreference.__init__(self, prefs, widget)
        FadingConditional.__init__(self)


class FadeMaxVolumePreference(widgets.SpinPreference, FadingConditional):
    name = 'plugin/multialarmclock/fade_max_volume'
    default = 100

    def __init__(self, prefs, widget):
        widgets.SpinPreference.__init__(self, prefs, widget)
        FadingConditional.__init__(self)


class FadeIncrementPreference(widgets.SpinPreference, FadingConditional):
    name = 'plugin/multialarmclock/fade_increment'
    default = 1

    def __init__(self, prefs, widget):
        widgets.SpinPreference.__init__(self, prefs, widget)
        FadingConditional.__init__(self)


class FadeTimePreference(widgets.SpinPreference, FadingConditional):
    name = 'plugin/multialarmclock/fade_time'
    default = 30

    def __init__(self, prefs, widget):
        widgets.SpinPreference.__init__(self, prefs, widget)
        FadingConditional.__init__(self)
