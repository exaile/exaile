
from xlgui.prefs import widgets
from xl.nls import gettext as _
import os

name = _('DAAP Server')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'daapserver_prefs.ui')

class PortPreference(widgets.SpinPrefsItem):
    default = 3689
    name = 'plugin/daapserver/port'
    
class NamePreference(widgets.PrefsItem):
    default = 'Exaile Share'
    name = 'plugin/daapserver/name'
    
class EnabledPreference(widgets.CheckPrefsItem):
    default = True
    name = 'plugin/daapserver/enabled'
    
class HostPreference(widgets.PrefsItem):
    default = '0.0.0.0'
    name = 'plugin/daapserver/host'
