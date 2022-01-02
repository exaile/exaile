import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _("Quickbuttons")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "qb_prefs.ui")


class EnqueueByDefault(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_enqueue_by_default"


class DisableNewTrack(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_disable_new_track_when_playing"


class RemoveItem(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_remove_item_when_played"


class AutoAdvance(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_auto_advance"


class AutoAdvanceDelay(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_auto_advance_delay"


class Equalizer(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_equalizer"


class AudioDevice(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_audio_device"


class AudioDevicePreview(widgets.CheckPreference):
    default = True
    name = "quickbuttons/btn_audio_device_preview"
