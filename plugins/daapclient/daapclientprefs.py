from xlgui.preferences import widgets
from xl.nls import gettext as _
import os

name = _('DAAP Client')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'daapclient_prefs.ui')


class Ipv6Preference(widgets.CheckPreference):
    default = False
    name = 'plugin/daapclient/ipv6'


class HistoryPreference(widgets.CheckPreference):
    default = True
    name = 'plugin/daapclient/history'
