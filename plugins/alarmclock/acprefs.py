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

name = _('Alarm Clock')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "acprefs_pane.glade")

class HourPreference(widgets.SpinPrefsItem):
    default = 12
    name = 'plugin/alarmclock/hour'

class MinutsPreference(widgets.SpinPrefsItem):
    default = 30
    name = 'plugin/alarmclock/minuts'

class MondayPreference(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/alarmclock/monday'

class TuesdayPreference(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/alarmclock/tuesday'

class ThursdayPreference(widgets.CheckPrefsItem):
    default = False 
    name = 'plugin/alarmclock/thursday'
    
class WednesdayPreference(widgets.CheckPrefsItem):
    default = False 
    name = 'plugin/alarmclock/wednesday'
    
class FridayPreference(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/alarmclock/friday'
    
class SaturdayPreference(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/alarmclock/saturday'
    

class SundayPreference(widgets.CheckPrefsItem):
    default = False
    name = 'plugin/alarmclock/sunday'
    
class FadingPreferencew(widgets.CheckPrefsItem):
    default = False 
    name = 'plugin/alarmclock/alarm_use_fading'

class MinVolumePreference(widgets.SpinPrefsItem):
    default = 0
    name = 'plugin/alarmclock/alarm_min_volume'
    
class MaxVolumePreference(widgets.SpinPrefsItem):
    default = 100
    name = 'plugin/alarmclock/alarm_max_volume'

class IncrementPreference(widgets.SpinPrefsItem):
    default = 1
    name = 'plugin/alarmclock/alarm_increment'

class TimerperIncPreference(widgets.SpinPrefsItem):
    default = 1
    name = 'plugin/alarmclock/alarm_timer_per_inc'


