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

import gobject
import gtk

from xl import (
    event,
    player,
    providers,
    settings,
    xdg
)
from xl.nls import gettext as _
from xlgui import guiutil, actions
from xlgui.widgets.info import TrackToolTip
from xlgui.widgets import rating, menu, menuitems, playlist


def __create_tray_context_menu():
    sep = menu.simple_separator
    items = []
    # Play/Pause
    items.append(menuitems.PlayPauseMenuItem('playback-playpause', after=[]))
    # Next
    items.append(menuitems.NextMenuItem('playback-next', after=[items[-1].name]))
    # Prev
    items.append(menuitems.PrevMenuItem('playback-prev', after=[items[-1].name]))
    # Stop
    items.append(menuitems.StopMenuItem('playback-stop', after=[items[-1].name]))
    # ----
    items.append(sep('playback-sep', [items[-1].name]))
    # Shuffle
    items.append(menuitems.ShuffleModesMenuItem('playlist-mode-shuffle', after=[items[-1].name]))
    # Repeat
    items.append(menuitems.RepeatModesMenuItem('playlist-mode-repeat', after=[items[-1].name]))
    # Dynamic
    items.append(menuitems.DynamicModesMenuItem('playlist-mode-dynamic', after=[items[-1].name]))
    # ----
    items.append(sep('playlist-mode-sep', [items[-1].name]))
    # Rating
    def rating_get_tracks_func(parent_obj, context):
        current = player.PLAYER.current
        if current:
            return [current]
        else:
            return []
    items.append(menuitems.RatingMenuItem('rating', [items[-1].name],
        rating_get_tracks_func))
    # Remove
    def remove_current_cb(widget, menuobj, parent_obj, context):
        pl = player.QUEUE.current_playlist
        if pl and pl.current == player.PLAYER.current:
            del pl[pl.current_position]
    items.append(menu.simple_menu_item('remove-current', [items[-1].name],
        _("Remove Current Track From Playlist"), 'gtk-remove', remove_current_cb))
    # ----
    items.append(sep('misc-actions-sep', [items[-1].name]))
    # Quit
    items.append(actions.application.quit.create_menu_item(after=[items[-1].name]))
    for item in items:
        providers.register('tray-icon-context', item)
__create_tray_context_menu()


class BaseTrayIcon(object):
    """
        Trayicon base, needs to be derived from
    """
    def __init__(self, main):
        self.main = main
        self.VOLUME_STEP = 5

        self.tooltip = TrackToolTip(
            self, display_progress=True, auto_update=True)

        self.menu = menu.ProviderMenu('tray-icon-context', self)
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

        self.disconnect_events()
        self.set_visible(False)

        event.log_event('tray_icon_toggled', self, False)

    def connect_events(self):
        """
            Connects various callbacks with events
        """
        self.connect('button-press-event', self.on_button_press_event)
        self.connect('scroll-event', self.on_scroll_event)

        event.add_callback(self.on_playback_change_state, 'playback_player_end')
        event.add_callback(self.on_playback_change_state, 'playback_track_start')
        event.add_callback(self.on_playback_change_state, 'playback_toggle_pause')
        event.add_callback(self.on_playback_change_state, 'playback_error')

    def disconnect_events(self):
        """
            Disconnects various callbacks from events
        """
        event.remove_callback(self.on_playback_change_state, 'playback_player_end')
        event.remove_callback(self.on_playback_change_state, 'playback_track_start')
        event.remove_callback(self.on_playback_change_state, 'playback_toggle_pause')
        event.remove_callback(self.on_playback_change_state, 'playback_error')

    def update_icon(self):
        """
            Updates icon appearance based
            on current playback state
        """
        if player.PLAYER.current is None:
            self.set_from_icon_name('exaile')
            self.set_tooltip(_('Exaile Music Player'))
        elif player.PLAYER.is_paused():
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

    def set_visible(self, visible):
        """
            Shows or hides the tray icon
        """
        pass

    def get_menu_position(self, menu, icon):
        """
            Returns coordinates for
            the best menu position
        """
        return (0, 0, False)

    def on_button_press_event(self, widget, event):
        """
            Toggles main window visibility and
            pause as well as opens the context menu
        """
        if event.button == 1:
            self.main.toggle_visible(bringtofront=True)
        if event.button == 2:
            actions.playback.playpause.activate()
        if event.button == 3:
            self.menu.popup(None, None, self.get_menu_position,
                event.button, event.time, self)

    def on_scroll_event(self, widget, event):
        """
            Changes volume and skips tracks on scroll
        """
        if event.state & gtk.gdk.SHIFT_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                actions.playback.prev.activate()
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                actions.playback.next.activate()
        else:
            if event.direction == gtk.gdk.SCROLL_UP:
                volume = player.PLAYER.get_volume()
                player.PLAYER.set_volume(volume + self.VOLUME_STEP)
                return True
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                volume = player.PLAYER.get_volume()
                player.PLAYER.set_volume(volume - self.VOLUME_STEP)
                return True
            elif event.direction == gtk.gdk.SCROLL_LEFT:
                actions.playback.prev.activate()
            elif event.direction == gtk.gdk.SCROLL_RIGHT:
                actions.playback.next.activate()

    def on_playback_change_state(self, event, player, current):
        """
            Updates tray icon appearance
            on playback state change
        """
        self.update_icon()


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

