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
        self._create_menu()

    def _create_menu(self):
        """
            Creates the menu
        """
        self.queue_item = self.append(_('Toggle Queue'), lambda *e: self.on_queue(),
            'exaile-queue-icon')

    def on_queue(self, selected=None):
        """
            Called when the user clicks the "toggle queue" item
        """
        if not selected:
            selected = self.widget.get_selected_tracks()
        current = self.queue.get_tracks()

        for track in selected:
            if track in current:
                current.remove(track)
            else:
                current.append(track)

        self.queue.clear()
        self.queue.add_tracks(current)
        if hasattr(self.widget, 'queue_draw'):
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

class TrackSelectMenu(GenericTrackMenu):
    """
        Menu for any panel that operates on selecting tracks, IE, Files panel
        and the Collection panel
    """
    def __init__(self, panel, main):
        """
            Initializes the menu
        """
        self.main = main
        GenericTrackMenu.__init__(self, panel,
            panel.controller.exaile.queue)

    def _create_menu(self):
        """
            Actually adds the menu items
        """
        self.append_item = self.append(_('Append to Current'), lambda *e:
            self.on_append_items(), 'gtk-add')
        self.queue_item = self.append(_('Queue Items'), lambda *e: self.on_queue(),
            'exaile-queue-icon')

    def on_append_items(self, selected=None):
        """
            Appends the selected tracks to the current playlist
        """
        if not selected:
            selected = self.widget.get_selected_tracks()

        pl = self.main.get_selected_playlist()
        if pl:
            pl.playlist.add_tracks(selected, add_duplicates=False)

    def on_queue(self, selected=None):
        """
            Called when the user clicks the "toggle queue" item
        """
        if not selected:
            selected = self.widget.get_selected_tracks()
        pl = self.main.get_selected_playlist()
        self.queue.add_tracks(selected, add_duplicates=False)
        if pl:
            pl.playlist.add_tracks(selected, add_duplicates=False)
            pl.list.queue_draw()

# these are stubbs for now
FilesPanelMenu = TrackSelectMenu
CollectionPanelMenu = TrackSelectMenu
