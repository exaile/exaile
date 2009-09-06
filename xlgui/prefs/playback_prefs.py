# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
#
# The developers of the Exaile media player hereby grant permission 
# for non-GPL compatible GStreamer and Exaile plugins to be used and 
# distributed together with GStreamer and Exaile. This permission is 
# above and beyond the permissions granted by the GPL license by which 
# Exaile is covered. If you modify this code, you may extend this 
# exception to your version of the code, but you are not obligated to 
# do so. If you do not wish to do so, delete this exception statement 
# from your version.
#
#
# The developers of the Exaile media player hereby grant permission 
# for non-GPL compatible GStreamer and Exaile plugins to be used and 
# distributed together with GStreamer and Exaile. This permission is 
# above and beyond the permissions granted by the GPL license by which 
# Exaile is covered. If you modify this code, you may extend this 
# exception to your version of the code, but you are not obligated to 
# do so. If you do not wish to do so, delete this exception statement 
# from your version.

from xlgui.prefs import widgets
from xl import xdg
from xl.nls import gettext as _
from xlgui import commondialogs

name = _('Playback')
ui = xdg.get_data_path('ui/playback_prefs_pane.ui')

class EnginePreference(widgets.ComboPrefsItem):
    default = "normal"
    name = 'player/engine'
    map = ["normal", "unified"]
    def __init__(self, prefs, widget):
        widgets.ComboPrefsItem.__init__(self, prefs, widget, use_map=True)

class AudioSinkPreference(widgets.ComboPrefsItem):
    default = "auto"
    name = 'player/audiosink'
    map = ["auto", "gconf", "alsa", "oss", "pulse", "jack"]
    def __init__(self, prefs, widget):
        widgets.ComboPrefsItem.__init__(self, prefs, widget, use_map=True)

class ResumePreference(widgets.CheckPrefsItem):
    default = True
    name = 'player/resume_playback'

class PausedPreference(widgets.CheckPrefsItem):
    default = False
    name = 'player/resume_paused' 

# The following only work on the Unified engine

class UserFadeTogglePreference(widgets.CheckPrefsItem):
    default = False
    name = 'player/user_fade_enabled' 

class UserFadeDurationPreference(widgets.SpinPrefsItem):
    default = 1000
    name = 'player/user_fade'

class CrossfadingPreference(widgets.CheckPrefsItem):
    default = False
    name = 'player/crossfading'

class CrossfadeDurationPreference(widgets.SpinPrefsItem):
    default = 1000
    name = 'player/crossfade_duration'

