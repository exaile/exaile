# Copyright (C) 2006 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import gtk
from xlgui import guiutil
from gettext import gettext as _

class GenericTrackMenu(guiutil.Menu):
    """
        A menu that can be subclassed to use on any widget that displays
        tracks and defines the "get_selected_tracks" method
    """
    def __init__(self, widget, queue):
        guiutil.Menu.__init__(self)
        self.widget = widget
        self.queue = queue

        self._add_queue_pixbuf()
        self.queue_item = self.append(_('Toggle Queue'), self.on_queue,
            'exaile-queue-icon')

    def on_queue(self, *e):
        """
            Called when the user clicks the "toggle queue" item
        """
        selected = self.widget.get_selected_tracks()
        current = self.queue.get_tracks()

        for track in selected:
            if track in current:
                current.remove(track)
            else:
                current.append(track)

        self.queue.clear()
        self.queue.add_tracks(current)
        self.widget.queue_draw()

    def _add_queue_pixbuf(self):
        """
            Creates the icon for "toggle queue"
        """
        window = gtk.Window()

        pixbuf = guiutil.get_text_icon(window, u'\u2610', 16, 16)
        icon_set = gtk.IconSet(pixbuf)

        factory = gtk.IconFactory()
        factory.add_default()
        factory.add('exaile-queue-icon', icon_set)

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class PlaylistMenu(GenericTrackMenu):
    """
        Menu for xlgui.playlist.Playlist
    """
    def __init__(self, playlist):
        GenericTrackMenu.__init__(self, playlist,
            playlist.controller.exaile.queue)
