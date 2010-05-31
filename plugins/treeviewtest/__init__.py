# Copyright (C) 2010 Aren Olson
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

from xl import event

from playlist import Playlist, PlaylistNotebook

import logging
logger = logging.getLogger(__name__)


WINDOW = None

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global WINDOW
    WINDOW = TestWindow(exaile)

def disable(exaile):
    global WINDOW
    WINDOW.destroy()
    WINDOW = None


class TestWindow(object):
    def __init__(self, exaile):
        self.exaile = exaile
        trs = exaile.collection
        pl = Playlist("test", trs)
        exaile.shortcut = pl
        self.window = gtk.Window()
        self.tabs = PlaylistNotebook()
        self.tabs.create_tab_from_playlist(pl)
        self.window.add(self.tabs)
        self.window.resize(800, 600)
        self.window.show_all()

    def destroy(self):
        self.window.destroy()



