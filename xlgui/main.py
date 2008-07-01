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
from xlgui import playlist, cover
from gettext import gettext as _
import xl.playlist

class NotebookTab(gtk.EventBox):
    """
        A notebook tab, complete with a close button
    """
    def __init__(self, main, notebook, title, page):
        """
            Initializes the tab
        """
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.connect('button_press_event', self.on_button_press)

        self.main = main
        self.nb = notebook
        self.title = title
        self.page = page
        self.tips = gtk.Tooltips()

        self.hbox = hbox = gtk.HBox(False, 5)
        self.add(hbox)

        self.label = gtk.Label(title)
        hbox.pack_start(self.label, False, False)

        self.button = btn = gtk.Button()
        btn.set_name('tab_close_button')
        btn.set_relief(gtk.RELIEF_NONE)
        btn.set_focus_on_click(False)
        btn.connect('clicked', self.do_close)
        btn.connect('button_press_event', self.on_button_press)
        self.tips.set_tip(btn, _("Close Tab"))
        image = gtk.Image()
        image.set_from_stock('gtk-close', gtk.ICON_SIZE_MENU)
        btn.add(image)
        hbox.pack_end(btn, False, False)

        self.show_all()

    def on_button_press(self, widget, event):
        """
            Called when the user clicks on the tab
        """
        pass

    def do_close(self, *args):
        """
            Called when the user clicks the close button on the tab
        """
        num = self.nb.page_num(self.page)
        self.nb.remove_page(num)

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
        self._setup_widgets()
        self._setup_hotkeys()
        self._connect_events()

        self.add_playlist()

    def add_playlist(self, pl=None):
        """
            Adds a playlist to the playlist tab

            @param pl: the xl.playlist.Playlist instance to add
        """
        if not pl:
            pl = xl.playlist.Playlist()
        name = pl.name
        pl = playlist.Playlist(self.controller, pl)
        tab = NotebookTab(self, self.playlist_notebook, name, pl)
        self.playlist_notebook.append_page(pl,
            tab)
        self.playlist_notebook.set_current_page(
            self.playlist_notebook.get_n_pages() - 1)
        pl.playlist.set_random(self.shuffle_toggle.get_active())

    def _setup_hotkeys(self):
        """
            Sets up accelerators that haven't been set up in glade
        """
        hotkeys = (
            ('<Control>W', lambda *e: self.close_playlist_tab()),
        )

        self.accel_group = gtk.AccelGroup()
        for key, function in hotkeys:
            key, mod = gtk.accelerator_parse(key)
            self.accel_group.connect_group(key, mod, gtk.ACCEL_VISIBLE,
                function)
        self.window.add_accel_group(self.accel_group)

    def _setup_widgets(self):
        """
            Sets up the various widgets
        """
        self.shuffle_toggle = self.xml.get_widget('shuffle_button')
        self.shuffle_toggle.set_active(self.settings.get_option('playback/shuffle',
            False))

        # cover box
        self.cover_event_box = self.xml.get_widget('cover_event_box')
        self.cover = cover.CoverWidget(self, self.controller.exaile.covers,
            self.controller.exaile.player)
        self.cover_event_box.add(self.cover)

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
            'on_shuffle_button_toggled': self.on_shuffle_button_toggled,
            'on_clear_playlist_button_clicked': self.on_clear_playlist,
            'on_playlist_notebook_remove': self.on_playlist_notebook_remove,
            'on_new_playlist_item_activated': lambda *e:
                self.add_playlist(),
        })        

        event.add_callback(self.draw_playlist, 'playback_end',
            self.controller.exaile.player)
        event.add_callback(self.on_playback_start, 'playback_start',
            self.controller.exaile.player) 

    def close_playlist_tab(self, tab=None):
        """
            Closes the tab specified
            @param tab: the tab number to close.  If no number is specified,
                the currently selected tab is closed
        """
        if tab is None:
            tab = self.playlist_notebook.get_current_page()
        self.playlist_notebook.remove_page(tab)

    def on_playlist_notebook_remove(self, notebook, widget):
        """
            Called when a tab is removed from the playlist notebook
        """
        if notebook.get_n_pages() == 0:
            self.add_playlist()

    def on_clear_playlist(self, *e):
        """
            Clears the current playlist tab
        """
        playlist = self.get_current_playlist()
        if not playlist: return
        playlist.playlist.remove_tracks(0, len(playlist.playlist))

    def on_shuffle_button_toggled(self, button):
        """
            Called when the user clicks the shuffle checkbox
        """
        self.settings['playback/shuffle'] = button.get_active()
        pl = self.get_current_playlist()
        if pl:
            pl.playlist.get_random(button.get_active())

    def get_current_playlist(self):
        """
            Returns the currently selected playlist
        """
        page = self.playlist_notebook.get_current_page()
        if page is None: return
        page = self.playlist_notebook.get_nth_page(page)
        return page

    def on_playback_start(self, type, player, object):
        """
            Called when playback starts
            Sets the currently playing track visible in the currently selected
            playlist if the user has chosen this setting
        """
        pl = self.get_current_playlist()
        if player.current in pl.playlist.ordered_tracks:
            path = (pl.playlist.index(player.current),)
            pl.list.scroll_to_cell(path)
            pl.list.set_cursor(path)
        self.draw_playlist(type, player, object)

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
        page.playlist.set_random(self.shuffle_toggle.get_active())

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

