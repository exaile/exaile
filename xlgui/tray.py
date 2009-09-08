# Copyright (C) 2008-2009 Adam Olsen 
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

import gobject, gtk

from xl import xdg, event, settings
from xl.nls import gettext as _
from xlgui import guiutil

class TrayIcon(gtk.StatusIcon):
    VOLUME_SCROLL_AMOUNT = 5

    def __init__(self, main):
        gtk.StatusIcon.__init__(self)

        self.controller = main.controller
        self.player = main.controller.exaile.player
        self.queue = main.controller.exaile.queue
        self.window = main.window
        self.main = main

        self.setup_menu()
        self.update_icon()

        self.connect('button-press-event', self._button_pressed)
        self.connect('scroll-event', self._scrolled)
        self.connect('query-tooltip', self._query_tooltip)

        event.add_callback(self.on_playback_change_state, 'playback_player_start')
        event.add_callback(self.on_playback_change_state, 'playback_toggle_pause')
        event.add_callback(self.on_playback_change_state, 'playback_player_end')
        event.add_callback(self.on_setting_change, 'option_set')
        event.log_event('tray_icon_toggled', self, True)

    def destroy(self):
        """
            Unhides the window and removes the tray icon
        """
        # FIXME: Allow other windows too
        if not self.window.get_property('visible'):
            self.window.deiconify()
            self.window.present()
        self.menu = None
        event.log_event('tray_icon_toggled', self, False)

    def update_icon(self):
        """
            Updates the tray icon according to the playback state
        """
        if self.player.current is None:
            self.set_from_icon_name('exaile')
            self.set_tooltip(_("Exaile Music Player"))
        elif self.player.is_paused():
            self.set_from_icon_name('exaile-pause')
        else:
            self.set_from_icon_name('exaile-play')

    def setup_menu(self):
        """
            Sets up the popup menu for the tray icon
        """
        self.menu = guiutil.Menu()

        self.playpause = self.menu.append(stock_id='gtk-media-play',
            callback=lambda *e: self._play_pause_clicked())
        self.menu.append(stock_id='gtk-media-next',
            callback=lambda *e: self.queue.next())
        self.menu.append(stock_id='gtk-media-previous',
            callback=lambda *e: self.queue.prev())
        self.menu.append(stock_id='gtk-media-stop',
            callback=lambda *e: self.player.stop())

        self.menu.append_separator()

        self.check_shuffle = gtk.CheckMenuItem(_("Shuffle playback order"))
        self.check_shuffle.set_active(settings.get_option('playback/shuffle', False))
        self.check_shuffle.connect('toggled', self.set_mode_toggles)
        self.menu.append_item(self.check_shuffle)
        
        self.check_repeat = gtk.CheckMenuItem(_("Repeat playlist"))
        self.check_repeat.set_active(settings.get_option('playback/repeat', False))
        self.check_repeat.connect('toggled', self.set_mode_toggles)
        self.menu.append_item(self.check_repeat)
        
        self.check_dynamic = gtk.CheckMenuItem(_("Dynamically add similar tracks"))
        self.check_dynamic.set_active(settings.get_option('playback/dynamic', False))
        self.check_dynamic.connect('toggled', self.set_mode_toggles)
        self.menu.append_item(self.check_dynamic)

        self.menu.append_separator()

        self.rating_item = guiutil.MenuRatingWidget(self._get_current_track_list)
        self.menu.append_item(self.rating_item)
        self.rm_item = self.menu.append(label=_("Remove current track from playlist"),
            stock_id='gtk-remove',
            callback=lambda *e: self._remove_current_song())
        
        self.menu.append_separator()

        self.menu.append(stock_id='gtk-quit',
            callback=lambda *e: self.controller.exaile.quit())

        event.add_callback(self.update_menu, 'playback_track_start')
    
    def _get_current_track_list(self):
        l = []
        l.append(self.player.current)
        return l
    
    def update_menu(self, type=None, object=None, data=None):
        track = self.player.current
        if not track or not self.player.is_playing():
            self.playpause.destroy()
            self.playpause = self.menu.prepend(stock_id='gtk-media-play',
                callback=lambda *e: self._play_pause_clicked())
        elif self.player.is_playing():
            self.playpause.destroy()
            self.playpause = self.menu.prepend(stock_id='gtk-media-pause',
                callback=lambda *e: self._play_pause_clicked())
        
        if track:
            self.rating_item.set_sensitive(True)
            self.rm_item.set_sensitive(True)
        else:
            self.rating_item.set_sensitive(False)
            self.rm_item.set_sensitive(False)

    def set_mode_toggles(self, menuitem):
        """
            Updates Shuffle, Repeat and Dynamic states
        """
        settings.set_option('playback/shuffle', self.check_shuffle.get_active())
        settings.set_option('playback/repeat', self.check_repeat.get_active())
        settings.set_option('playback/dynamic', self.check_dynamic.get_active())

    def _remove_current_song(self):
        _pl = self.controller.main.get_current_playlist ().playlist
        if _pl and self.player.current:
            _pl.remove (_pl.index (self.player.current))

    def on_playback_change_state(self, event, player, current):
        """
            Updates the tray icon on playback state change
        """
        self.update_icon()

    def on_setting_change(self, event, object, option):
        """
            Updates the toggle states
        """
        if option == 'playback/shuffle':
            self.check_shuffle.set_active(settings.get_option(option, False))
        
        if option == 'playback/repeat':
            self.check_repeat.set_active(settings.get_option(option, False))

        if option == 'playback/dynamic':
            self.check_dynamic.set_active(settings.get_option(option, False))

    def _button_pressed(self, icon, event):
        if event.button == 1:
            self.main.toggle_visible()
        if event.button == 2:
            self._play_pause_clicked()
        if event.button == 3:
            self.update_menu()
            self.menu.popup(None, None, None,
                event.button, event.time, self)
    
    def _play_pause_clicked(self):
        if self.player.is_paused() or self.player.is_playing():
            self.player.toggle_pause()
        else:
            pl = self.controller.main.get_selected_playlist()
            self.queue.set_current_playlist(pl.playlist)
            if pl:
                track = pl.get_selected_track()
                if track:
                    pl.playlist.set_current_pos(
                        pl.playlist.index(track))
            self.queue.play()

    def _query_tooltip(self, *e):
        if settings.get_option('osd/hover_tray', False):
            self.controller.main.osd.show(self.player.current)

    def _scrolled(self, icon, event):
        if event.state & gtk.gdk.SHIFT_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                self.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                self.queue.next()
        else:
            if event.direction == gtk.gdk.SCROLL_UP:
                volume = self.player.get_volume()
                self.player.set_volume(volume + self.VOLUME_SCROLL_AMOUNT)
                return True
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                volume = self.player.get_volume()
                self.player.set_volume(volume - self.VOLUME_SCROLL_AMOUNT)
                return True
            elif event.direction == gtk.gdk.SCROLL_LEFT:
                self.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_RIGHT:
                self.queue.next()

