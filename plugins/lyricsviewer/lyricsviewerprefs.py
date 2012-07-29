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

name = _('Lyrics Viewer')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, 'lyricsviewer_prefs.ui')

class LyricsFontPreference(widgets.FontButtonPreference):
    default = 'Sans 9'
    name = 'plugin/lyricsviewer/lyrics_font'
