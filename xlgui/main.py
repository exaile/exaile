# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

import pygtk
pygtk.require('2.0')
import gtk, gtk.glade, gobject
from xl import xdg, event
import xl.playlist
from xlgui import playlist
from gettext import gettext as _

class MainWindow(object):
    """
        Main Exaile Window
    """
    def __init__(self, controller):
        """
            Initializes the main window

            @param controller: the main gui controller
        """
        self.controller = controller
        self.settings = controller.exaile.settings
        self.first_removed = False

        self.xml = gtk.glade.XML(xdg.get_data_path("glade/main.glade"),
            'ExaileWindow', 'exaile')
        self.window = self.xml.get_widget('ExaileWindow')
        self.window.set_title(_('Exaile'))
        self.panel_notebook = self.xml.get_widget('panel_notebook')
        self.playlist_notebook = self.xml.get_widget('playlist_notebook')
        self.playlist_notebook.remove_page(0)
        self.splitter = self.xml.get_widget('splitter')

        self._setup_position()
        self._connect_events()

        pl = xl.playlist.Playlist()
        self.add_playlist(pl)

    def add_playlist(self, pl):
        """
            Adds a playlist to the playlist tab

            @param pl: the xl.playlist.Playlist instance to add
        """
        name = pl.name
        pl = playlist.Playlist(self.controller, pl)
        self.playlist_notebook.append_page(pl,
            gtk.Label(name))
        self.playlist_notebook.set_current_page(
            self.playlist_notebook.get_n_pages() - 1)

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.splitter.connect('notify::position', self.configure_event)
        self.xml.signal_autoconnect({
            'on_configure_event':   self.configure_event,
            'on_delete_event':      self.delete_event,
            'on_quit_item_activated': self.delete_event,
            'on_playlist_notebook_switch':  self.playlist_switch_event,
            'on_play_button_clicked': self.on_play_clicked,
            'on_next_button_clicked':
                lambda *e: self.controller.exaile.queue.next(),
            'on_prev_button_clicked':
                lambda *e: self.controller.exaile.queue.prev(),
            'on_stop_button_clicked':
                lambda *e: self.controller.exaile.player.stop(),
        })        

        event.add_callback(self.draw_playlist, 'playback_end')
        event.add_callback(self.draw_playlist, 'playback_start') 

    def draw_playlist(self, *e):
        """
            Called when playback starts, redraws teh playlist
        """
        page = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(page)
        gobject.idle_add(page.queue_draw)

    def on_play_clicked(self, *e):
        """
            Called when the play button is clicked
        """
        exaile = self.controller.exaile
        if exaile.player.is_paused() or exaile.player.is_playing():
            exaile.player.toggle_pause()
        else:
            exaile.queue.play()

    def playlist_switch_event(self, notebook, page, page_num):
        """
            Called when the page is changed in the playlist notebook
        """
        page = notebook.get_nth_page(page_num)
        self.controller.exaile.queue.set_current_playlist(page.playlist)

    def _setup_position(self):
        """
            Sets up the position and sized based on the size the window was
            when it was last moved or resized
        """
        width = self.settings.get_option('gui/mainw_width', 500)
        height = self.settings.get_option('gui/mainw_height', 600)
        x = self.settings.get_option('gui/mainw_x', 10)
        y = self.settings.get_option('gui/mainw_y', 10)

        self.window.move(x, y)
        self.window.resize(width, height)

        pos = self.settings.get_option('gui/mainw_sash_pos', 200)
        self.splitter.set_position(pos)

    def delete_event(self, *e):
        """
            Called when the user attempts to close the window
        """
        self.window.hide()
        gobject.idle_add(self.controller.exaile.quit)
        return True

    def configure_event(self, *e):
        """
            Called when the window is resized or moved
        """
        (width, height) = self.window.get_size()
        self.settings['gui/mainw_height'] = height
        self.settings['gui/mainw_width'] = width
        (x, y) = self.window.get_position()
        self.settings['gui/mainw_x'] = x
        self.settings['gui/mainw_y'] = y

        pos = self.splitter.get_position()
        if pos > 10:
            self.settings['gui/mainw_sash_pos'] = pos

        return False

    def add_panel(self, child, name):
        """
            Adds a panel to the panel notebook
        """
        label = gtk.Label(name)
        label.set_angle(90)
        self.panel_notebook.append_page(child, label)

        if not self.first_removed:
            self.first_removed = True

            # the first tab in the panel is a stub that just stops libglade from
            # complaining
            self.panel_notebook.remove_page(0)

