# Copyright (C) 2006-2010  Johannes Sasongko <sasongko@gmail.com>
# Copyright (C) 2010  Mathias Brodala <info@noctus.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _('Desktop Cover')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "desktopcover_preferences.ui")
icon = 'image-x-generic'


class AnchorPreference(widgets.ComboPreference):
    default = 'topleft'
    name = 'plugin/desktopcover/anchor'


class XPreference(widgets.SpinPreference):
    default = 0
    name = 'plugin/desktopcover/x'


class YPreference(widgets.SpinPreference):
    default = 0
    name = 'plugin/desktopcover/y'


class OverrideSizePreference(widgets.CheckPreference):
    default = False
    name = 'plugin/desktopcover/override_size'


class SizePreference(widgets.SpinPreference, widgets.CheckConditional):
    default = 200
    name = 'plugin/desktopcover/size'
    condition_preference_name = 'plugin/desktopcover/override_size'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)


class FadingPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/desktopcover/fading'


class FadingDurationPreference(widgets.SpinPreference, widgets.CheckConditional):
    default = 50
    name = 'plugin/desktopcover/fading_duration'
    condition_preference_name = 'plugin/desktopcover/fading'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)


# vi: et sts=4 sw=4 tw=80
