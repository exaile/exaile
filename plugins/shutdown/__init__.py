# Copyright (C) 2010 Johannes Schwarz
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import dbus
from gi.repository import GLib
from gi.repository import Gtk

from xl import event, providers, settings
from xl.nls import gettext as _
from xlgui.widgets import dialogs, menu

from . import shutdown_preferences

SHUTDOWN = None


class Shutdown:
    def __init__(self, exaile):
        self.exaile = exaile
        self.do_shutdown = False
        self.do_close = settings.get_option(
            "shutdown/activate_closing_by_default", False
        )

        # add menuitem to tools menu
        providers.register(
            'menubar-tools-menu',
            menu.simple_separator('plugin-sep-shutdown', ['slow-scan-collection']),
        )

        item = menu.check_menu_item(
            'close',
            ['plugin-sep-shutdown'],
            _('Close Exaile after Playback'),
            #   checked func                # callback func
            lambda *x: self.do_close,
            lambda w, n, p, c: self.on_toggle(w, n),
        )
        providers.register('menubar-tools-menu', item)

        if self.do_close:
            event.add_ui_callback(self.on_playback_player_end, 'playback_player_end')

        item = menu.check_menu_item(
            'shutdown',
            ['close'],
            _('Shutdown after Playback'),
            #   checked func                # callback func
            lambda *x: self.do_shutdown,
            lambda w, n, p, c: self.on_toggle(w, n),
        )
        providers.register('menubar-tools-menu', item)

        self.countdown = None
        self.counter = 10

        self.message = dialogs.MessageBar(
            parent=exaile.gui.builder.get_object('player_box'),
            buttons=Gtk.ButtonsType.CLOSE,
        )
        self.message.connect('response', self.on_response)

    def on_toggle(self, menuitem, name):
        if menuitem.get_active() and name == 'close':
            self.do_close = True
            self.do_shutdown = False
            self.message.show_info(
                _('Close scheduled'),
                _('Exaile will be closed at the end of playback.'),
            )
        elif menuitem.get_active() and name == 'shutdown':
            self.do_close = False
            self.do_shutdown = True
            self.message.show_info(
                _('Shutdown scheduled'),
                _('Computer will be shutdown at the end of playback.'),
            )
        else:
            self.disable_all()

        if self.do_close or self.do_shutdown:
            event.add_ui_callback(self.on_playback_player_end, 'playback_player_end')

    def disable_all(self):
        self.do_shutdown = False
        self.do_close = False
        event.remove_callback(self.on_playback_player_end, 'playback_player_end')

        # Stop possible countdown
        if self.countdown is not None:
            GLib.source_remove(self.countdown)
            self.countdown = None

        # Prepare for a new run
        self.counter = 10

        # Reset message button layout
        self.message.hide()
        self.message.clear_buttons()
        self.message.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)

    def on_playback_player_end(self, event, player, track):
        """
        Tries to shutdown the computer
        """
        self.message.set_message_type(Gtk.MessageType.INFO)
        if self.do_close:
            self.message.set_markup(_('Imminent Closing'))
        else:
            self.message.set_markup(_('Imminent Shutdown'))
        self.message.clear_buttons()
        self.message.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)

        if self.countdown is not None:
            GLib.source_remove(self.countdown)

        self.counter = settings.get_option("shutdown/timeout", 10)
        self.countdown = GLib.timeout_add_seconds(1, self.on_timeout)

    def on_response(self, widget, response):
        """
        Cancels shutdown if requested
        """
        if response == Gtk.ResponseType.CANCEL:
            self.disable_all()

    def on_timeout(self):
        """
        Tries to shutdown the computer
        """
        if self.counter > 0:
            msg_close = _('Exaile will be closed in %d seconds.') % self.counter
            msg_shutdown = (
                _('The computer will be shut down in %d seconds.') % self.counter
            )

            if self.do_close:
                msg = msg_close
            elif self.do_shutdown:
                msg = msg_shutdown
            else:
                return False

            self.message.set_secondary_text(msg)
            self.message.show()

            self.counter -= 1

            return True

        if self.do_close:
            self.do_close = False
            self.exaile.quit()
            return  # Should not be necessary

        self.do_shutdown = False

        bus = dbus.SystemBus()

        try:
            proxy = bus.get_object('org.freedesktop.login1', '/org/freedesktop/login1')
            proxy.PowerOff(False, dbus_interface='org.freedesktop.login1.Manager')
        except dbus.exceptions.DBusException:
            try:
                proxy = bus.get_object(
                    'org.freedesktop.ConsoleKit', '/org/freedesktop/ConsoleKit/Manager'
                )
                proxy.Stop(dbus_interface='org.freedesktop.ConsoleKit.Manager')
            except dbus.exceptions.DBusException:
                try:
                    proxy = bus.get_object(
                        'org.freedesktop.Hal', '/org/freedesktop/Hal/devices/computer'
                    )
                    proxy.Shutdown(
                        dbus_interface='org.freedesktop.Hal.Device.SystemPowerManagement'
                    )
                except dbus.exceptions.DBusException:
                    self.message.show_warning(
                        _('Shutdown failed'),
                        _('Computer could not be shutdown using D-Bus.'),
                    )

    def destroy(self):
        """
        Cleans up
        """
        if self.countdown is not None:
            GLib.source_remove(self.countdown)

        event.remove_callback(self.on_playback_player_end, 'playback_player_end')
        for item in providers.get('menubar-tools-menu'):
            if item.name == 'shutdown' or item.name == 'close':
                providers.unregister('menubar-tools-menu', item)


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def _enable(eventname, exaile, nothing):
    global SHUTDOWN
    SHUTDOWN = Shutdown(exaile)


def disable(exaile):
    global SHUTDOWN
    SHUTDOWN.destroy()


def get_preferences_pane():
    return shutdown_preferences
