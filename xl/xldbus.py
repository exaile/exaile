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

import dbus, dbus.service, gobject, sys
from optparse import OptionParser

def check_dbus(bus, interface):
    obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
    dbus_iface = dbus.Interface(obj, 'org.freedesktop.DBus')
    avail = dbus_iface.ListNames()
    return interface in avail

def check_exit(options, args):
    """
        Check to see if dbus is running, and if it is, call the appropriate
        methods
    """
    do_exit = False
    if not options.new:
        # TODO: handle dbus stuff
        bus = dbus.SessionBus()
        if check_dbus(bus, 'org.exaile.ExaileInterface'):
            remote_object = bus.get_object('org.exaile.ExaileInterface', 
                '/org/exaile')
            iface = dbus.Interface(remote_object,
                'org.exaile.ExaileInterface')
            iface.test_service('testing dbus service')

            # check for one argument, if it doesn't begin with a it's probably
            # a url
            args = sys.argv[2:]
            if not [x for x in args if x.startswith('-')]:
                for arg in args:
                    iface.play_file(arg)

            info_commands = ('get_artist', 'get_title', 'get_album',
                'get_length', 'get_rating')
            for command in info_commands:
                if getattr(options, command):
                    print iface.get_track_attr(command.replace('get_', ''))
                    do_exit = True

            run_commands = ('play', 'stop', 'next', 'prev', 'play_pause')
            for command in run_commands:
                if getattr(options, command):
                    getattr(iface, command)()
                    sys.exit(0)

            other_commands = ('current_position', )
            for command in other_commands:
                if getattr(options, command):
                    val = getattr(iface, command)()
                    if val is not None:
                        print val
                    do_exit = True

            if not do_exit:
                print "You have entered an invalid option"

            return True

    return False

class DbusManager(dbus.service.Object):
    """
        The dbus interface object for Exaile
    """
    def __init__(self, exaile):
        """
            Initilializes the interface
        """
        self.exaile = exaile
        self.bus = dbus.SessionBus()
        self.bus_name = dbus.service.BusName('org.exaile.ExaileInterface',
            bus=self.bus)
        dbus.service.Object.__init__(self, self.bus_name, "/org/exaile")

    @dbus.service.method('org.exaile.ExaileInterface', 's')
    def test_service(self, arg):
        """
            Just test the dbus object
        """
        print arg

    @dbus.service.method('org.exaile.ExaileInterface', 's')
    def get_track_attr(self, attr):
        """
            Returns a attribute of a track
        """
        try:
            value = self.exaile.player.current[attr]
        except ValueError:
            value = None
        if value:
            return unicode(value)
        return u''

    @dbus.service.method("org.exaile.ExaileInterface")
    def prev(self):
        """
            Jumps to the previous track
        """
        self.exaile.queue.prev()

    @dbus.service.method("org.exaile.ExaileInterface")
    def stop(self):
        """
            Stops playback
        """
        self.exaile.player.stop()

    @dbus.service.method("org.exaile.ExaileInterface")
    def next(self):
        """
            Jumps to the next track
        """
        self.exaile.queue.next()

    @dbus.service.method("org.exaile.ExaileInterface")
    def play(self):
        """
            Starts playback
        """
        self.exaile.queue.play()

    @dbus.service.method("org.exaile.ExaileInterface")
    def play_pause(self):
        """
            Toggle Play or Pause
        """
        self.exaile.player.toggle_pause()

    @dbus.service.method("org.exaile.ExaileInterface", None, "i")
    def current_position(self):
        """
            Returns the position inside the current track as a percentage
        """
        return self.exaile.player.get_progress()*100

    @dbus.service.method("org.exaile.ExaileInterface", None, "s")
    def get_version(self):
        return self.exaile.get_version()

    @dbus.service.method("org.exaile.ExaileInterface", "s")
    def play_file(self, filename):
        """
            Plays the specified file
        """
        self.exaile.gui.open_uri(filename)
