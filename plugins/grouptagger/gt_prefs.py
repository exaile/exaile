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
from xl.nls import gettext as _
import os
from gi.repository import Gtk

name = _('GroupTagger')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'gt_prefs.ui')


def _get_system_default_font():
    return Gtk.Widget.get_default_style().font_desc.to_string()


class GTPanelFontPreference(widgets.FontButtonPreference):
    default = _get_system_default_font()
    name = 'plugin/grouptagger/panel_font'


class GTPanelFontResetButtonPreference(widgets.FontResetButtonPreference):
    default = _get_system_default_font()
    name = 'plugin/grouptagger/reset_button'
    condition_preference_name = 'plugin/grouptagger/panel_font'


class GTGroupingTagName(widgets.ComboPreference):
    default = 'grouping'
    name = 'plugin/grouptagger/tagname'
