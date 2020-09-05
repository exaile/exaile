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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import sys

from xl.nls import gettext as _
from xlgui.preferences import widgets


name = _('On Screen Display')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "osd_preferences.ui")
icon = 'dialog-information'


OSDPLUGIN = None


def page_enter(_preferencesdialog):
    """
    Shows a preview of the OSD
    """
    OSDPLUGIN.make_osd_editable(True)


def page_leave(_preferencesdialog):
    """
    Hides the OSD preview
    """
    OSDPLUGIN.make_osd_editable(False)


class ShowProgressPreference(widgets.CheckPreference):
    name = 'plugin/osd/show_progress'
    default = True


class DisplayDurationPreference(widgets.SpinPreference):
    name = 'plugin/osd/display_duration'
    default = 4


class BackgroundPreference(widgets.RGBAButtonPreference):
    name = 'plugin/osd/background'
    default = 'rgba(18, 18, 18, 0.8)'

    def __init__(self, preferences, widget):
        widgets.RGBAButtonPreference.__init__(self, preferences, widget)
        if sys.platform.startswith("win32"):
            # Setting opacity on Windows crashes with segfault,
            # see https://bugzilla.gnome.org/show_bug.cgi?id=674449
            widget.set_use_alpha(False)


class FormatPreference(widgets.TextViewPreference):
    name = 'plugin/osd/format'
    default = _(
        '<span font_desc="Sans 11" foreground="#fff">$title</span>\n'
        'by $artist\n'
        'from $album'
    )


class BorderRadiusPreference(widgets.SpinPreference):
    name = 'plugin/osd/border_radius'
    default = 10

    def _get_value(self):
        return self.widget.get_value_as_int()
