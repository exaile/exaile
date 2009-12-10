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

import gobject
import gtk

from xl import event, settings, xdg
from xl.nls import gettext as _
from xlgui import guiutil
import xlgui.main

class BaseTrayIcon(object):
    """
        Trayicon base, needs to be derived from
    """
    def __init__(self, main):
        self.main = main
        self.player = main.controller.exaile.player
        self.queue = main.controller.exaile.queue
        self.VOLUME_STEP = 5

        self.setup_menu()
        self.update_icon()
        self.connect_events()
        event.log_event('tray_icon_toggled', self, True)

    def destroy(self):
        """
            Unhides the window and removes the tray icon
        """
        # FIXME: Allow other windows too
        if not self.main.window.get_property('visible'):
            self.main.window.deiconify()
            self.main.window.present()
        self.set_visible(False)
        self.menu = None
        event.log_event('tray_icon_toggled', self, False)

    def setup_menu(self):
        """
            Sets up the popup menu for the tray icon
        """
        self.menu = guiutil.Menu()

        self.playpause_menuitem = self.menu.append(stock_id='gtk-media-play',
            callback=lambda *e: self._play_pause_clicked())
        self.menu.append(stock_id='gtk-media-next',
            callback=lambda *e: self.queue.next())
        self.menu.append(stock_id='gtk-media-previous',
            callback=lambda *e: self.queue.prev())
        self.menu.append(stock_id='gtk-media-stop',
            callback=lambda *e: self.player.stop())

        self.menu.append_separator()

        self.shuffle_menuitem = gtk.CheckMenuItem(_('Shuffle playback order'))
        self.shuffle_menuitem.set_active(settings.get_option('playback/shuffle', False))
        self.menu.append_item(self.shuffle_menuitem)

        self.repeat_menuitem = gtk.CheckMenuItem(_('Repeat playlist'))
        self.repeat_menuitem.set_active(settings.get_option('playback/repeat', False))
        self.menu.append_item(self.repeat_menuitem)

        self.dynamic_menuitem = gtk.CheckMenuItem(_('Dynamically add similar tracks'))
        self.dynamic_menuitem.set_active(settings.get_option('playback/dynamic', False))
        self.menu.append_item(self.dynamic_menuitem)

        self.menu.append_separator()

        self.rating_menuitem = guiutil.MenuRatingWidget(
            lambda: [self.player.current],
            self.get_current_track_rating
        )
        self.menu.append_item(self.rating_menuitem)
        self.remove_menuitem = self.menu.append(
            label=_('Remove current track from playlist'),
            stock_id='gtk-remove',
            callback=lambda *e: self.remove_current_track()
        )

        self.menu.append_separator()

        self.menu.append(stock_id='gtk-quit',
            callback=lambda *e: self.main.quit())

    def connect_events(self):
        """
            Connects various events with callbacks
        """
        self.connect('button-press-event', self.on_button_press_event)
        self.connect('scroll-event', self.on_scroll_event)

        self.shuffle_menuitem.connect('toggled', self.on_checkmenuitem_toggled)
        self.repeat_menuitem.connect('toggled', self.on_checkmenuitem_toggled)
        self.dynamic_menuitem.connect('toggled', self.on_checkmenuitem_toggled)

        event.add_callback(self.on_playback_change_state, 'playback_player_start')
        event.add_callback(self.on_playback_change_state, 'playback_toggle_pause')
        event.add_callback(self.on_playback_change_state, 'playback_player_end')
        #event.add_callback(self.update_menu, 'playback_track_start')
        event.add_callback(self.on_setting_change, 'option_set')

    def update_menu(self):
        """
            Updates the context menu
        """
        current_track = self.player.current

        # TODO: Do better than this
        if current_track is None or not self.player.is_playing():
            self.playpause_menuitem.destroy()
            self.playpause_menuitem = self.menu.prepend(
                stock_id='gtk-media-play',
                callback=lambda *e: self.play_pause()
            )
        elif self.player.is_playing():
            self.playpause_menuitem.destroy()
            self.playpause_menuitem = self.menu.prepend(
                stock_id='gtk-media-pause',
                callback=lambda *e: self.play_pause()
            )

        self.rating_menuitem.on_rating_change()

        if current_track is None:
            self.rating_menuitem.set_sensitive(False)
            self.remove_menuitem.set_sensitive(False)
        else:
            self.rating_menuitem.set_sensitive(True)
            self.remove_menuitem.set_sensitive(True)

    def update_icon(self):
        """
            Updates icon appearance based
            on current playback state
        """
        if self.player.current is None:
            self.set_from_icon_name('exaile')
            self.set_tooltip(_('Exaile Music Player'))
        elif self.player.is_paused():
            self.set_from_icon_name('exaile-pause')
        else:
            self.set_from_icon_name('exaile-play')

    def set_from_icon_name(self, icon_name):
        """
            Updates the tray icon
        """
        pass
    
    def set_tooltip(self, tooltip_text):
        """
            Updates the tray icon tooltip
        """
        pass

    def get_menu_position(self, menu, icon):
        """
            Returns coordinates for
            the best menu position
        """
        return (0, 0, False)

    def play_pause(self):
        """
            Starts or pauses playback
        """
        if self.player.is_paused() or self.player.is_playing():
            self.player.toggle_pause()
        else:
            gplaylist = xlgui.main.get_selected_playlist()
            playlist = gplaylist.playlist

            if gplaylist is not None:
                self.queue.set_current_playlist(playlist)
                track = gplaylist.get_selected_track()

                if track is not None:
                    playlist.set_current_pos(playlist.index(track))

            self.queue.play()

    def remove_current_track(self):
        """
            Removes the currently playing track
        """
        playlist = self.main.get_selected_playlist()

        if playlist is not None and self.player.current is not None:
            playlist.remove_tracks([self.player.current])

    def get_current_track_rating(self):
        """
            Returns the rating of the current track
        """
        if self.player.current is not None:
            return self.player.current.get_rating()

        return 0

    def on_button_press_event(self, widget, event):
        """
            Toggles main window visibility and
            pause as well as opens the context menu
        """
        if event.button == 1:
            self.main.toggle_visible()
        if event.button == 2:
            self.play_pause()
        if event.button == 3:
            self.update_menu()
            self.menu.popup(None, None, self.get_menu_position,
                event.button, event.time, self)

    def on_checkmenuitem_toggled(self, widget):
        """
            Updates Shuffle, Repeat and Dynamic states
        """
        settings.set_option('playback/shuffle', self.shuffle_menuitem.get_active())
        settings.set_option('playback/repeat', self.repeat_menuitem.get_active())
        settings.set_option('playback/dynamic', self.dynamic_menuitem.get_active())

    def on_scroll_event(self, widget, event):
        """
            Changes volume and skips tracks on scroll
        """
        if event.state & gtk.gdk.SHIFT_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                self.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                self.queue.next()
        else:
            if event.direction == gtk.gdk.SCROLL_UP:
                volume = self.player.get_volume()
                self.player.set_volume(volume + self.VOLUME_STEP)
                return True
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                volume = self.player.get_volume()
                self.player.set_volume(volume - self.VOLUME_STEP)
                return True
            elif event.direction == gtk.gdk.SCROLL_LEFT:
                self.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_RIGHT:
                self.queue.next()

    def on_playback_change_state(self, event, player, current):
        """
            Updates tray icon appearance
            on playback state change
        """
        self.update_icon()

    def on_setting_change(self, event, object, option):
        """
            Updates the toggle states
        """
        if option == 'playback/shuffle':
            self.shuffle_menuitem.set_active(settings.get_option(option, False))

        if option == 'playback/repeat':
            self.repeat_menuitem.set_active(settings.get_option(option, False))

        if option == 'playback/dynamic':
            self.dynamic_menuitem.set_active(settings.get_option(option, False))

class TrayIcon(gtk.StatusIcon, BaseTrayIcon):
    """
        Wrapper around GtkStatusIcon
    """
    def __init__(self, main):
        gtk.StatusIcon.__init__(self)
        BaseTrayIcon.__init__(self, main)

    def get_menu_position(self, menu, icon):
        """
            Returns coordinates for
            the best menu position
        """
        return gtk.status_icon_position_menu(menu, icon)

