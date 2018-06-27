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

import os
import sys

from xlgui.preferences import widgets
from xl.nls import gettext as _

name = _('IPython Console')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'ipconsole_prefs.ui')
icon = 'utilities-terminal'


class OpacityPreference(widgets.ScalePreference):
    default = 80.0
    name = 'plugin/ipconsole/opacity'

    def __init__(self, preferences, widget):
        widgets.ScalePreference.__init__(self, preferences, widget)
        if sys.platform.startswith("win32"):
            self.set_widget_sensitive(False)
            # Setting opacity on Windows crashes with segfault,
            # see https://bugzilla.gnome.org/show_bug.cgi?id=674449
            self.widget.set_tooltip(
                _("Opacity cannot be set on Windows due to a bug in Gtk+")
            )


class FontPreference(widgets.FontButtonPreference):
    default = 'Monospace 10'
    name = 'plugin/ipconsole/font'


class TextColor(widgets.RGBAButtonPreference):
    default = 'lavender'
    name = 'plugin/ipconsole/text_color'


class BgColor(widgets.RGBAButtonPreference):
    default = 'black'
    name = 'plugin/ipconsole/background_color'


class AutoStart(widgets.CheckPreference):
    default = False
    name = 'plugin/ipconsole/autostart'
