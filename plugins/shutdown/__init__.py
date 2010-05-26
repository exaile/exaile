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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
import dbus
import gtk
try:
    import pynotify
except ImportError:
    pynotify = None
    from xlgui.widgets import dialogs
from xl import event
from xl.nls import gettext as _
from xlgui import icons

SHUTDOWN = None

class Shutdown():
    def __init__(self, exaile):
        self.exaile = exaile
        self.menu_item = gtk.CheckMenuItem(_('Shutdown after Playback'))
        self.menu_item.connect('toggled', self.on_toggled)
        self.menu_item.set_tooltip_text(_('Shutdown computer at the end of playback'))
        exaile.gui.builder.get_object('tools_menu').append(self.menu_item)
        self.menu_item.show()

    def on_toggled(self, menuitem):
        """
            Enables or disables defered shutdown
        """
        if menuitem.get_active():
            event.add_callback(self.on_playback_player_end, 'playback_player_end')

            if pynotify:
                pynotify.init('Exaile')
                notification = pynotify.Notification(_('<b>Shutdown scheduled</b>'),
                    _('Computer will be shutdown at the end of playback.'))
                notification.set_icon_from_pixbuf(icons.MANAGER.pixbuf_from_stock(
                    gtk.STOCK_QUIT, gtk.ICON_SIZE_DIALOG))
                notification.show()
            else:
                dialogs.info(None, _('<b>Shutdown scheduled</b>\n\n'
                    'Computer will be shutdown at the end of playback.'))
        else:
            event.remove_callback(self.on_playback_player_end, 'playback_player_end')

    def on_playback_player_end(self, event, player, track):
        """
            Tries to shutdown the computer
        """
        bus = dbus.SystemBus()

        try:
            remote_object = bus.get_object('org.freedesktop.Hal',
                '/org/freedesktop/Hal/devices/computer')
            remote_object.Shutdown(dbus_interface='org.freedesktop.Hal.Device.SystemPowerManagement')
        except dbus.exceptions.DBusException:
            if pynotify:
                pynotify.init('Exaile')
                notification = pynotify.Notification(_('<b>Shutdown failed</b>'),
                    _('Computer could not be shutdown using D-Bus.'))
                notification.set_icon_from_pixbuf(icons.MANAGER.pixbuf_from_stock(
                    gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG))
                notification.show()
            else:
                dialogs.error(None, _('<b>Shutdown failed</b>\n\n'
                    'Computer could not be shutdown using D-Bus.'))

    def destroy(self):
        """
            Cleans up
        """
        event.remove_callback(self.on_playback_player_end, 'playback_player_end')
        self.menu_item.hide()
        self.menu_item.destroy()

def enable(exaile):
    if (exaile.loading):
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    global SHUTDOWN
    SHUTDOWN = Shutdown(exaile)

def disable(exaile):
    global SHUTDOWN
    SHUTDOWN.destroy()

