# screensaverpause - pauses Exaile playback on screensaver activation
# Copyright (C) 2009-2011  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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

from gi.repository import GLib

import dbus
from xl import event, player, settings

SERVICES = [
    dict(  # GNOME
        bus_name='org.gnome.ScreenSaver',
        path='/org/gnome/ScreenSaver',
        dbus_interface='org.gnome.ScreenSaver',
    ),
    dict(  # MATE
        bus_name='org.mate.ScreenSaver',
        path='/org/mate/ScreenSaver',
        dbus_interface='org.mate.ScreenSaver',
    ),
    dict(  # CINNAMON
        bus_name='org.cinnamon.ScreenSaver',
        path='/org/cinnamon/ScreenSaver',
        dbus_interface='org.cinnamon.ScreenSaver',
    ),
    dict(  # XFCE
        bus_name='org.xfce.ScreenSaver',
        path='/org/xfce/ScreenSaver',
        dbus_interface='org.xfce.ScreenSaver',
    ),
    dict(  # KDE
        bus_name='org.freedesktop.ScreenSaver',
        path='/',
        dbus_interface='org.freedesktop.ScreenSaver',
    ),
]

from . import prefs


def get_preferences_pane():
    return prefs


matches = set()
bus = None
was_playing = None


def screensaver_active_changed(is_active):
    global was_playing
    if is_active:
        was_playing = player.PLAYER.is_playing()
        player.PLAYER.pause()
    elif was_playing and settings.get_option("screensaverpause/unpause", 0):
        player.PLAYER.unpause()


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable()


def _enable(*a):
    global bus
    bus = dbus.SessionBus()
    for service in SERVICES:
        matches.add(
            bus.add_signal_receiver(
                screensaver_active_changed, signal_name='ActiveChanged', **service
            )
        )


def disable(exaile):
    if bus is None:
        return
    for match in frozenset(matches):
        match.remove()
        matches.remove(match)


def test():
    import dbus.mainloop.glib as dbgl

    dbgl.DBusGMainLoop(set_as_default=True)

    global bus
    bus = dbus.SessionBus()

    for service in SERVICES:
        try:
            proxy = bus.get_object(
                service['bus_name'], service['path'], follow_name_owner_changes=True
            )
        except dbus.DBusException:
            continue
        break
    else:
        return None
    assert proxy
    interface = dbus.Interface(proxy, service['dbus_interface'])
    mainloop = GLib.MainLoop()

    def active_changed(new_value):
        if not new_value:
            mainloop.quit()

    interface.connect_to_signal('ActiveChanged', screensaver_active_changed)

    # For some reason Lock never returns.
    interface.Lock(ignore_reply=True)

    mainloop.run()


if __name__ == '__main__':
    test()


# vi: et sts=4 sw=4 tw=80
