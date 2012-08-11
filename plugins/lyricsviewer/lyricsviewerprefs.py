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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from xlgui.preferences import widgets
from xl import xdg
from xl.nls import gettext as _
import os
import gtk

name = _('Lyrics Viewer')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'lyricsviewer_prefs.ui')

def _get_system_default_font():
    return gtk.widget_get_default_style().font_desc.to_string()

class LyricsFontPreference(widgets.FontButtonPreference):
    default = _get_system_default_font()
    name = 'plugin/lyricsviewer/lyrics_font'

class ResetButton(widgets.Button, widgets.Conditional):
    name = 'plugin/lyricsviewer/reset_button'
    condition_preference_name = 'plugin/lyricsviewer/lyrics_font'

    def __init__(self, preferences, widget):
	widgets.Button.__init__(self, preferences, widget)
	widgets.Conditional.__init__(self)

    def on_check_condition(self):
	if (self.condition_widget.get_font_name() == _get_system_default_font()):
		return False
	return True

    def on_clicked(self, button):
	self.condition_widget.set_font_name(_get_system_default_font())
	self.condition_widget.emit('font-set')
