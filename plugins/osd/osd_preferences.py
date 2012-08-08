# Copyright (C) 2012 Mathias Brodala
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

import gtk.gdk
import os

from xl.nls import gettext as _
from xlgui.preferences import widgets

from alphacolor import (
    AlphaColor,
    alphacolor_parse
)

name = _('On Screen Display')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "osd_preferences.ui")
icon = 'gtk-info'

class ShowProgressPreference(widgets.CheckPreference):
    name = 'plugin/osd/show_progress'
    default = True

class DisplayDurationPreference(widgets.SpinPreference):
    name = 'plugin/osd/display_duration'
    default = 4

class BackgroundPreference(widgets.ColorButtonPreference):
    name = 'plugin/osd/background'
    default = '#333333cc'

    def __init__(self, preferences, widget):
        widgets.ColorButtonPreference.__init__(self, preferences, widget)
        self.widget.set_use_alpha(True)

    def _set_value(self):
        color = alphacolor_parse(
            self.preferences.settings.get_option(self.name, self.default))

        self.widget.set_color(gtk.gdk.Color(color.red, color.green, color.blue))
        self.widget.set_alpha(color.alpha)

    def _get_value(self):
        color = self.widget.get_color()
        color = AlphaColor(
            color.red,
            color.green,
            color.blue,
            self.widget.get_alpha()
        )

        return str(color)

class FormatPreference(widgets.TextViewPreference):
    name = 'plugin/osd/format'
    default = _('<span font_desc="Sans 11" foreground="#fff">$title</span>\n'
                'by $artist\n'
                'from $album')

