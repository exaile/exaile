# Copyright (C) 2008-2010 Adam Olsen
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import gtk

from xl import xdg
from xl.nls import gettext as _
from xlgui import icons
from xlgui.preferences import widgets

name = _('Playlists')
icon = icons.MANAGER.pixbuf_from_icon_name(
    'music-library', gtk.ICON_SIZE_SMALL_TOOLBAR)
ui = xdg.get_data_path('ui', 'preferences', 'playlists.ui')

class OpenLastPreference(widgets.CheckPreference):
    default = True
    name = 'playlist/open_last'

class AskSaveCustomPlaylistPreference(widgets.CheckPreference):
    default = True
    name = 'playlist/ask_save'

class ReplaceContentPreference(widgets.CheckPreference):
    default = False
    name = 'playlist/replace_content'
    
class AppendStartsPlaybackPreference(widgets.CheckPreference):
    default = False
    name = 'playlist/append_menu_starts_playback'

# FIXME: Is this still relevant?
#class QueueSavePreferences(widgets.CheckPreference):
#    default = True
#    name = 'playlist/save_queue'

#    def change(self, *e):
#        dialogs.error(self.preferences.window, "Doesn't work yet")

# vim: et sts=4 sw=4
