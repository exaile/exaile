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

name = _('Alarm Clock')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "acprefs_pane.ui")


class HourPreference(widgets.SpinPreference):
    default = 12
    name = 'plugin/alarmclock/hour'


class MinutesPreference(widgets.SpinPreference):
    default = 30
    name = 'plugin/alarmclock/minuts'


class MondayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/monday'


class TuesdayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/tuesday'


class WednesdayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/wednesday'


class ThursdayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/thursday'


class FridayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/friday'


class SaturdayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/saturday'


class SundayPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/sunday'


class FadingPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/alarmclock/alarm_use_fading'


class MinVolumePreference(widgets.SpinPreference):
    default = 0
    name = 'plugin/alarmclock/alarm_min_volume'


class MaxVolumePreference(widgets.SpinPreference):
    default = 100
    name = 'plugin/alarmclock/alarm_max_volume'


class IncrementPreference(widgets.SpinPreference):
    default = 1
    name = 'plugin/alarmclock/alarm_increment'


class TimerStepPreference(widgets.SpinPreference):
    default = 1
    name = 'plugin/alarmclock/alarm_timer_per_inc'
