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

import logging

from gi.repository import Gdk
from gi.repository import Gtk

from xl import event, player, providers, settings
from xl.nls import gettext as _
from xlgui.widgets.info import TrackToolTip
from xlgui.widgets import menu, menuitems, playlist, playback
from xlgui import guiutil

logger = logging.getLogger(__name__)


def is_supported():
    """
    On some platforms (e.g. Linux+Wayland) tray icons are not supported.
    """
    supported = not guiutil.platform_is_wayland()

    if not supported:
        logger.debug("No tray icon support on this platform")

    return supported


def __create_tray_context_menu():
    sep = menu.simple_separator
    items = []
    # Play/Pause
    items.append(
        playback.PlayPauseMenuItem('playback-playpause', player.PLAYER, after=[])
    )
    # Next
    items.append(
        playback.NextMenuItem('playback-next', player.PLAYER, after=[items[-1].name])
    )
    # Prev
    items.append(
        playback.PrevMenuItem('playback-prev', player.PLAYER, after=[items[-1].name])
    )
    # Stop
    items.append(
        playback.StopMenuItem('playback-stop', player.PLAYER, after=[items[-1].name])
    )
    # ----
    items.append(sep('playback-sep', [items[-1].name]))
    # Shuffle
    items.append(
        playlist.ShuffleModesMenuItem('playlist-mode-shuffle', after=[items[-1].name])
    )
    # Repeat
    items.append(
        playlist.RepeatModesMenuItem('playlist-mode-repeat', after=[items[-1].name])
    )
    # Dynamic
    items.append(
        playlist.DynamicModesMenuItem('playlist-mode-dynamic', after=[items[-1].name])
    )
    # ----
    items.append(sep('playlist-mode-sep', [items[-1].name]))
    # Rating

    def rating_get_tracks_func(parent, context):
        current = player.PLAYER.current
        if current:
            return [current]
        else:
            return []

    items.append(
        menuitems.RatingMenuItem('rating', [items[-1].name], rating_get_tracks_func)
    )
    # Remove
    items.append(playlist.RemoveCurrentMenuItem([items[-1].name]))
    # ----
    items.append(sep('misc-actions-sep', [items[-1].name]))
    # Quit

    def quit_cb(*args):
        from xl import main

        main.exaile().quit()

    items.append(
        menu.simple_menu_item(
            'quit-application',
            [items[-1].name],
            _("_Quit Exaile"),
            'application-exit',
            callback=quit_cb,
        )
    )
    for item in items:
        providers.register('tray-icon-context', item)


__create_tray_context_menu()


class BaseTrayIcon:
    """
    Trayicon base, needs to be derived from
    """

    def __init__(self, main):
        self.main = main
        self.VOLUME_STEP = 0.05

        self.tooltip = TrackToolTip(self, player.PLAYER)
        self.tooltip.set_auto_update(True)
        self.tooltip.set_display_progress(True)

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
        self.tooltip.destroy()
        event.log_event('tray_icon_toggled', self, False)

    def connect_events(self):
        """
        Connects various callbacks with events
        """
        self.connect('button-press-event', self.on_button_press_event)
        self.connect('scroll-event', self.on_scroll_event)

        event.add_ui_callback(
            self.on_playback_change_state, 'playback_player_end', player.PLAYER
        )
        event.add_ui_callback(
            self.on_playback_change_state, 'playback_track_start', player.PLAYER
        )
        event.add_ui_callback(
            self.on_playback_change_state, 'playback_toggle_pause', player.PLAYER
        )
        event.add_ui_callback(
            self.on_playback_change_state, 'playback_error', player.PLAYER
        )

    def disconnect_events(self):
        """
        Disconnects various callbacks from events
        """
        event.remove_callback(
            self.on_playback_change_state, 'playback_player_end', player.PLAYER
        )
        event.remove_callback(
            self.on_playback_change_state, 'playback_track_start', player.PLAYER
        )
        event.remove_callback(
            self.on_playback_change_state, 'playback_toggle_pause', player.PLAYER
        )
        event.remove_callback(
            self.on_playback_change_state, 'playback_error', player.PLAYER
        )

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

    def on_button_press_event(self, widget, event):
        """
        Toggles main window visibility and
        pause as well as opens the context menu
        """
        if event.button == Gdk.BUTTON_PRIMARY:
            self.main.toggle_visible(bringtofront=True)
        if event.button == Gdk.BUTTON_MIDDLE:
            playback.playpause(player.PLAYER)
        if event.triggers_context_menu():
            self.menu.popup_at_pointer(event)

    def on_scroll_event(self, widget, event):
        """
        Changes volume and skips tracks on scroll
        """
        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            if event.direction == Gdk.ScrollDirection.UP:
                player.QUEUE.prev()
            elif event.direction == Gdk.ScrollDirection.DOWN:
                player.QUEUE.next()
        else:
            if event.direction == Gdk.ScrollDirection.UP:
                volume = settings.get_option('player/volume', 1)
                settings.set_option('player/volume', min(volume + self.VOLUME_STEP, 1))
                return True
            elif event.direction == Gdk.ScrollDirection.DOWN:
                volume = settings.get_option('player/volume', 1)
                settings.set_option('player/volume', max(0, volume - self.VOLUME_STEP))
                return True
            elif event.direction == Gdk.ScrollDirection.LEFT:
                player.QUEUE.prev()
            elif event.direction == Gdk.ScrollDirection.RIGHT:
                player.QUEUE.next()

    def on_playback_change_state(self, event, player, current):
        """
        Updates tray icon appearance
        on playback state change
        """
        self.update_icon()


class TrayIcon(Gtk.StatusIcon, BaseTrayIcon):
    """
    Wrapper around GtkStatusIcon
    """

    def __init__(self, main):
        Gtk.StatusIcon.__init__(self)
        BaseTrayIcon.__init__(self, main)

    def set_tooltip(self, tooltip_text):
        """
        Updates the tray icon tooltip
        """
        self.set_tooltip_text(tooltip_text)
