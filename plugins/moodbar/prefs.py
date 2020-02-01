# moodbar - Replace Exaile's seekbar with a moodbar
# Copyright (C) 2018  Johannes Sasongko <sasongko@gmail.com>
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

from xl.nls import gettext as _
from xlgui.preferences import widgets


PLUGINDIR = os.path.dirname(os.path.realpath(__file__))

name = _('Moodbar')
ui = os.path.join(PLUGINDIR, "prefs.ui")


class UseWaveformPreference(widgets.CheckPreference):
    name = 'plugin/moodbar/use_waveform'
    default = False


class UseTintPreference(widgets.CheckPreference):
    name = 'plugin/moodbar/use_tint'
    default = False


class TintPreference(widgets.RGBAButtonPreference, widgets.CheckConditional):
    name = 'plugin/moodbar/tint'
    condition_preference_name = 'plugin/moodbar/use_tint'
    default = 'rgba(255, 255, 255, 0.2)'

    def __init__(self, preferences, widget):
        widgets.RGBAButtonPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)


# vi: et sts=4 sw=4 tw=99
