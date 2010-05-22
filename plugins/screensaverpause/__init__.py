# screensaverpause - pauses/resumes Exaile playback on screensaver start/stop
# Copyright (C) 2010  Johannes Sasongko <sasongko@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import dbus, gtk
from xl import event

SERVICES = [
    dict( # GNOME
        bus_name='org.gnome.ScreenSaver',
        path='/org/gnome/ScreenSaver',
        dbus_interface='org.gnome.ScreenSaver',
    ),
    dict( # KDE
        bus_name='org.freedesktop.ScreenSaver',
        path='/',
        dbus_interface='org.freedesktop.ScreenSaver',
    ),
]

matches = set()
bus = None
exaile = None
was_playing = None

def active_changed(new_value):
    if new_value:
        global was_playing
        was_playing = exaile.player.pause()
    elif was_playing:
        exaile.player.unpause()

def enable(exaile_):
    global exaile
    exaile = exaile_
    if exaile_.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable()

def _enable(*a):
    global bus
    try:
        bus = dbus.SessionBus()
    except dbus.DBusException:
        # TODO: log
        return
    for service in SERVICES:
        matches.add(bus.add_signal_receiver(active_changed,
            signal_name='ActiveChanged', **service))

def disable(exaile):
    if bus is None: return
    for match in frozenset(matches):
        match.remove()
        matches.remove(match)


def test():
    import glib
    glib.threads_init()
    import dbus.mainloop.glib as dbgl
    dbgl.DBusGMainLoop(set_as_default=True)

    global bus
    bus = dbus.SessionBus()

    for service in SERVICES:
        try:
            proxy = bus.get_object(service['bus_name'], service['path'],
                follow_name_owner_changes=True)
        except dbus.DBusException:
            continue
        break
    else:
        return None
    assert proxy
    interface = dbus.Interface(proxy, service['dbus_interface'])
    mainloop = glib.MainLoop()

    def active_changed(new_value):
        if not new_value:
            mainloop.quit()
    interface.connect_to_signal('ActiveChanged', active_changed)

    # For some reason Lock never returns.
    interface.Lock(ignore_reply=True)

    mainloop.run()

if __name__ == '__main__':
    test()


# vi: et sts=4 sw=4 tw=80
