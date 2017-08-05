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
from xl import xdg

name = _('Lyrics Viewer')
ui = xdg.get_data_path('ui', 'preferences', 'lyrics.ui')


DEFAULT_FONT = None


class LyricsFontPreference(widgets.FontButtonPreference):
    default = None
    name = 'plugin/lyricsviewer/lyrics_font'

    def __init__(self, preferences, widget):
        self.default = DEFAULT_FONT
        widgets.FontButtonPreference.__init__(self, preferences, widget)


class LyricsFontResetButtonPreference(widgets.FontResetButtonPreference):
    default = None
    name = 'plugin/lyricsviewer/reset_button'
    condition_preference_name = 'plugin/lyricsviewer/lyrics_font'

    def __init__(self, preferences, widget):
        self.default = DEFAULT_FONT
        widgets.FontResetButtonPreference.__init__(self, preferences, widget)
