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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

from gi.repository import Gtk

from xl.nls import gettext as _
from xl import main, playlist, event
from xlgui.widgets import dialogs

from xlgui.widgets.playlist import PlaylistPageBase, PlaylistView


class QueuePage(PlaylistPageBase):
    def __init__(self, container, player):
        PlaylistPageBase.__init__(self)
        self.plcontainer = container
        self.player = player
        self.playlist = player.queue  # a queue is a playlist object...

        self.swindow = Gtk.ScrolledWindow()
        self.swindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(self.swindow, True, True, 0)

        self.view = PlaylistView(self.player.queue, self.player)
        self.view.dragdrop_copyonly = True
        self.swindow.add(self.view)

        event.add_ui_callback(
            self.on_length_changed,
            'playlist_current_position_changed',
            self.player.queue,
        )
        event.add_ui_callback(
            self.on_length_changed, "playlist_tracks_added", self.player.queue
        )
        event.add_ui_callback(
            self.on_length_changed, "playlist_tracks_removed", self.player.queue
        )

        self.show_all()

    def on_length_changed(self, *args):
        self.name_changed()
        if len(self.player.queue) == 0:
            self.tab.set_closable(True)
        else:
            self.plcontainer.show_queue(switch=False)
            self.tab.set_closable(False)

    ## NotebookPage API ##

    def focus(self):
        self.view.grab_focus()

    def get_page_name(self):
        qlen = self.player.queue.queue_length()
        if qlen == -1:
            return _("Queue")
        else:
            return _("Queue (%d)") % qlen

    def set_tab(self, tab):
        super(QueuePage, self).set_tab(tab)
        tab.set_closable(not self.do_closing())

    def do_closing(self):
        """
        Allows closing only if the queue is empty
        """
        return len(self.player.queue) != 0

    ## End NotebookPage ##

    def on_saveas(self):
        exaile = main.exaile()
        name = dialogs.ask_for_playlist_name(exaile.gui.main.window, exaile.playlists)
        if name is not None:
            pl = playlist.Playlist(name, self.playlist[:])
            exaile.playlists.save_playlist(pl)
            self.plcontainer.create_tab_from_playlist(pl)


# vim: et sw=4 st=4
