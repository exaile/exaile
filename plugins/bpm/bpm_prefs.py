import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _("BPM Counter")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "bpm_prefs.ui")


class ShowConfimation(widgets.CheckPreference):
    default = True
    name = "plugin/bpm/show_confirmation_on_manual_setting"
