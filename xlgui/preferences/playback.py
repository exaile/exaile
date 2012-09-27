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
from xl.player import pipe
from xl.nls import gettext as _

name = _('Playback')
icon = gtk.STOCK_MEDIA_PLAY
ui = xdg.get_data_path('ui', 'preferences', 'playback.ui')

class EnginePreference(widgets.ComboPreference):
    default = "normal"
    name = 'player/engine'
    restart_required = True

class AudioSinkPreference(widgets.ComboPreference):
    default = "auto"
    name = 'player/audiosink'
    restart_required = True
    
    def __init__(self, preferences, widget):
        widgets.ComboPreference.__init__(self, preferences, widget)
        model = self.widget.get_model()
        
        # always list auto first
        def _sink_cmp(x,y):
            if x[0] == y[0] or 'auto' not in (x[0],y[0]):
                return cmp(x[0],y[0])
            if x[0] == 'auto':
                return -1
            return 1
                
        for name, preset in sorted(pipe.SINK_PRESETS.iteritems(), _sink_cmp):
            model.append((name, preset['name']))
        self._set_value()

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
        
class SelectDeviceForSinkPreference(widgets.ComboPreference, widgets.Conditional):
    default = ''
    name = "player/audiosink_device"
    condition_preference_name = 'player/audiosink'

    restart_required = True

    def __init__(self, preferences, widget):
        widgets.ComboPreference.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)

    def on_check_condition(self):
        iter = self.condition_widget.get_active_iter()
        value = self.condition_widget.get_model().get_value(iter, 0)        

        devices = pipe.sink_enumerate_devices(value)
        if devices:
            # disable because the clear() causes a settings write
            self.is_enabled = False

            model = self.widget.get_model()
            model.clear()

            for device in devices:
                model.append(device) 

            self.is_enabled = True
            self._set_value()
            return True

        self.is_enabled = False
        return False

    def on_condition_met(self):
        self.widget.get_parent().show()

    def on_condition_failed(self):
        self.widget.get_parent().hide()
        self.widget.get_model().clear()

    def _setup_changed(self):
        self.widget.connect('changed', self._change)

    def _change(self, *args):
        if self.is_enabled:
            self.change(args)

    def _get_value(self):
        if self.is_enabled:
            return widgets.ComboPreference._get_value(self)
        return ''

class ResumePreference(widgets.CheckPreference):
    default = True
    name = 'player/resume_playback'

class PausedPreference(widgets.CheckPreference):
    default = False
    name = 'player/resume_paused'
    
class EnqueueBeginsPlayback(widgets.CheckPreference):
    default = True
    name = 'queue/enqueue_begins_playback'
    
class RemoveQueuedItemWhenPlayed(widgets.CheckPreference):
    default = True
    name = 'queue/remove_item_when_played'

class EngineConditional(widgets.Conditional):
    """
        True if the specified engine is selected
    """
    condition_preference_name = 'player/engine'
    conditional_engine = ''

    def on_check_condition(self):
        """
            Specifies the condition to meet

            :returns: Whether the condition is met or not
            :rtype: bool
        """
        iter = self.condition_widget.get_active_iter()
        value = self.condition_widget.get_model().get_value(iter, 0)

        if value == self.conditional_engine:
            return True

        return False
    
class AutoAdvancePlayer(widgets.CheckPreference, EngineConditional):
    default = True
    name = 'player/auto_advance'
    conditional_engine = 'normal'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)
    
class AutoAdvanceDelay(widgets.SpinPreference, widgets.MultiConditional):
    default = 0
    name = "player/auto_advance_delay"
    condition_preference_names = ['player/auto_advance', 'player/engine']
    
    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        widgets.MultiConditional.__init__(self)
        
    def on_check_condition(self):
        if not self.condition_widgets['player/auto_advance'].get_active():
            return False
            
        iter = self.condition_widgets['player/engine'].get_active_iter()
        value = self.condition_widgets['player/engine'].get_model().get_value(iter, 0)

        if value == 'normal':
            return True

        return False

class UserFadeTogglePreference(widgets.CheckPreference, EngineConditional):
    default = False
    name = 'player/user_fade_enabled'
    conditional_engine = 'unified'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)

class UserFadeDurationPreference(widgets.SpinPreference, EngineConditional):
    default = 1000
    name = 'player/user_fade'
    conditional_engine = 'unified'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)

class CrossfadingPreference(widgets.CheckPreference, EngineConditional):
    default = False
    name = 'player/crossfading'
    conditional_engine = 'unified'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)

class CrossfadeDurationPreference(widgets.SpinPreference, EngineConditional):
    default = 1000
    name = 'player/crossfade_duration'
    conditional_engine = 'unified'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)

# vim: et sts=4 sw=4
