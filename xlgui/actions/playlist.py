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


from xl.playlist import Playlist

from xlgui.actions import _base
from xlgui import main
from xlgui.widgets.playlist import PlaylistPage

def get_current_playlist():
    page = main.mainwindow().get_current_page()
    if not isinstance(page, PlaylistPage):
        return None
    return page

def insert_sep(l, pos=1):
    l = l[:]
    l.insert(pos, "----")
    return l

shuffle_mode = _base.ChoiceAction("playlist-shuffle", _("Shuffle"),
    "media-playlist-shuffle", insert_sep(Playlist.shuffle_modes),
    insert_sep(Playlist.shuffle_mode_names))
def on_shuffle_mode_changed(action, index):
    page = get_current_playlist()
    if page:
        page.shuffle_mode = action.choices[index]
shuffle_mode.connect('changed', on_shuffle_mode_changed)

repeat_mode = _base.ChoiceAction("playlist-repeat", _("Repeat"),
    "media-playlist-repeat", insert_sep(Playlist.repeat_modes),
    insert_sep(Playlist.repeat_mode_names))
def on_repeat_mode_changed(action, index):
    page = get_current_playlist()
    if page:
        page.repeat_mode = action.choices[index]
repeat_mode.connect('changed', on_shuffle_mode_changed)

dynamic_mode = _base.ToggleAction("playlist-dynamic", _("Dynamic"),
    "media-playlist-dynamic")
def on_dynamic_mode_toggled(action):
    page = get_current_playlist()
    if page:
        if action.props.active:
            page.dynamic_mode = 'enabled'
        else:
            page.dynamic_mode = 'disabled'
dynamic_mode.connect('toggled', on_dynamic_mode_toggled)


