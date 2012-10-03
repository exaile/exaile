# Copyright (C) 2012 Brian Parma
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xlgui.preferences import widgets
from xl import xdg
from xl.nls import gettext as _
import os

name = _('IPython Console')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'ipconsole_prefs.ui')
icon = 'utilities-terminal'

class OpacityPreference(widgets.ScalePreference):
    default = 80.0
    name = 'plugin/ipconsole/opacity'

class FontPreference(widgets.FontButtonPreference):
    default = 'Monospace 10'
    name = 'plugin/ipconsole/font'
    
class TextColor(widgets.ColorButtonPreference):
    default = 'lavender'
    name = 'plugin/ipconsole/text_color'
    
class BgColor(widgets.ColorButtonPreference):
    default = 'black'
    name = 'plugin/ipconsole/background_color'
    
class Theme(widgets.ComboPreference):
    default = 'Linux'
    name = 'plugin/ipconsole/iptheme'
