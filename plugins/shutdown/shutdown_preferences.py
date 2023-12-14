import os
from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _("Shutdown")
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "shutdown_preferences.ui")


class ActivateClosingByDefault(widgets.CheckPreference):
    default = False
    name = "shutdown/activate_closing_by_default"


class Timeout(widgets.SpinPreference):
    default = 10
    name = "shutdown/timeout"
