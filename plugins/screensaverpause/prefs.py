import os
from xl.nls import gettext as _
from xlgui.preferences import widgets

name = _("Pause on Screensaver")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'prefs.ui')


class Unpause(widgets.CheckPreference):
    default = False
    name = 'screensaverpause/unpause'
