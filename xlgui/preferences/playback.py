# Copyright (C) 2008-2010 Adam Olsen
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

import gobject
import gtk

from xlgui.preferences import widgets
from xl import main, xdg
from xl.nls import gettext as _

name = _('Playback')
ui = xdg.get_data_path('ui', 'preferences', 'playback.ui')

class EnginePreference(widgets.ComboPreference):
    default = "normal"
    name = 'player/engine'
    restart_required = True

class AudioSinkPreference(widgets.ComboPreference):
    default = "auto"
    name = 'player/audiosink'
    restart_required = True

class CustomAudioSinkPreference(widgets.Preference, widgets.Conditional):
    default = ""
    name = "player/custom_sink_pipe"
    condition_preference_name = 'player/audiosink'

    def __init__(self, preferences, widget):
        widgets.Preference.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)

    def on_check_condition(self):
        """
            Specifies a condition to meet

            :returns: Whether the condition is met or not
            :rtype: bool
        """
        iter = self.condition_widget.get_active_iter()
        value = self.condition_widget.get_model().get_value(iter, 0)

        if value == 'custom':
            return True

        return False

class ResumePreference(widgets.CheckPreference):
    default = True
    name = 'player/resume_playback'

class PausedPreference(widgets.CheckPreference):
    default = False
    name = 'player/resume_paused'

class UnifiedConditional(widgets.Conditional):
    """
        True if the unified engine is selected
    """
    condition_preference_name = 'player/engine'

    def on_check_condition(self):
        """
            Specifies the condition to meet

            :returns: Whether the condition is met or not
            :rtype: bool
        """
        iter = self.condition_widget.get_active_iter()
        value = self.condition_widget.get_model().get_value(iter, 0)

        if value == 'unified':
            return True

        return False

class UserFadeTogglePreference(widgets.CheckPreference, UnifiedConditional):
    default = False
    name = 'player/user_fade_enabled'
    condition_preference_name = 'player/engine'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        UnifiedConditional.__init__(self)

class UserFadeDurationPreference(widgets.SpinPreference, UnifiedConditional):
    default = 1000
    name = 'player/user_fade'
    condition_preference_name = 'player/engine'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        UnifiedConditional.__init__(self)

class CrossfadingPreference(widgets.CheckPreference, UnifiedConditional):
    default = False
    name = 'player/crossfading'
    condition_preference_name = 'player/engine'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        UnifiedConditional.__init__(self)

class CrossfadeDurationPreference(widgets.SpinPreference, UnifiedConditional):
    default = 1000
    name = 'player/crossfade_duration'
    condition_preference_name = 'player/engine'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        UnifiedConditional.__init__(self)

# vim: et sts=4 sw=4
