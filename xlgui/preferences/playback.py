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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

from xlgui.preferences import widgets
from xl import common, xdg
from xl.nls import gettext as _

# TODO: If we ever add another engine, need to make sure that
#       gstreamer-specific stuff doesn't accidentally get loaded
from xl.player.gst.sink import get_devices, SINK_PRESETS

name = _('Playback')
icon = 'media-playback-start'
ui = xdg.get_data_path('ui', 'preferences', 'playback.ui')


class EnginePreference(widgets.ComboPreference):
    default = "gstreamer"
    name = 'player/engine'
    restart_required = True


class AudioSinkPreference(widgets.ComboPreference):
    default = "auto"
    name = 'player/audiosink'

    def __init__(self, preferences, widget):
        widgets.ComboPreference.__init__(self, preferences, widget)
        model = self.widget.get_model()

        # always list auto first, custom last
        def keyfunc(item):
            name = item[0]
            if name == 'auto':
                return common.LowestStr(name)
            elif name == 'custom':
                return common.HighestStr(name)
            else:
                return name

        for name, preset in sorted(SINK_PRESETS.items(), key=keyfunc):
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
        return self.get_condition_value() == 'custom'

    def on_condition_met(self):
        self.show_widget()

    def on_condition_failed(self):
        self.hide_widget()


class SelectDeviceForSinkPreference(widgets.ComboPreference, widgets.Conditional):
    default = 'auto'
    name = "player/audiosink_device"
    condition_preference_name = 'player/audiosink'

    def __init__(self, preferences, widget):
        self.is_enabled = False
        widgets.ComboPreference.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)

    def on_check_condition(self):
        return self.get_condition_value() == 'auto'

    def on_condition_met(self):

        # disable because the clear() causes a settings write
        self.is_enabled = False

        model = self.widget.get_model()
        if model is None:
            return

        model.clear()

        for device_name, device_id, _create_audiosink_cb in get_devices():
            model.append((device_id, device_name))

        self.is_enabled = True
        self._set_value()

        self.show_widget()
        self.set_widget_sensitive(True)

    def on_condition_failed(self):
        if self.get_condition_value() == 'custom':
            self.hide_widget()
        else:
            self.show_widget()
            self.set_widget_sensitive(False)
        self.is_enabled = False
        model = self.widget.get_model()
        if model:
            model.clear()

    def done(self):
        return self.is_enabled

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


class DisableNewTrackWhenPlaying(widgets.CheckPreference):
    default = False
    name = 'queue/disable_new_track_when_playing'


class GaplessPlayback(widgets.CheckPreference):
    default = True
    name = 'player/gapless_playback'


class EngineConditional(widgets.Conditional):
    """
    True if the specified engine is selected
    """

    condition_preference_name = 'player/engine'
    conditional_engine = ''

    def on_check_condition(self):
        if self.get_condition_value() == self.conditional_engine:
            return True

        return False


class AutoAdvancePlayer(widgets.CheckPreference, EngineConditional):
    default = True
    name = 'player/auto_advance'
    conditional_engine = 'gstreamer'

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

        if self.get_condition_value('player/engine') == 'gstreamer':
            return True

        return False


class UserFadeTogglePreference(widgets.CheckPreference, EngineConditional):
    default = False
    name = 'player/user_fade_enabled'
    conditional_engine = 'gstreamer'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)


class UserFadeDurationPreference(widgets.SpinPreference, EngineConditional):
    default = 1000
    name = 'player/user_fade'
    conditional_engine = 'gstreamer'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)


class CrossfadingPreference(widgets.CheckPreference, EngineConditional):
    default = False
    name = 'player/crossfading'
    conditional_engine = 'gstreamer'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)


class CrossfadeDurationPreference(widgets.SpinPreference, EngineConditional):
    default = 1000
    name = 'player/crossfade_duration'
    conditional_engine = 'gstreamer'

    def __init__(self, preferences, widget):
        widgets.SpinPreference.__init__(self, preferences, widget)
        EngineConditional.__init__(self)


# vim: et sts=4 sw=4
