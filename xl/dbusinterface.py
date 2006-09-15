# Copyright (C) 2006 Adam Olsen
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

import sys
import dbus
import dbus.service
import dbus.glib, gst
import gobject

class DBusInterfaceObject(dbus.service.Object):
    """
        A DBus service for exaile
    """
    def __init__(self, bus_name, exaile,
        object_path="/DBusInterfaceObject"):
        """
            Initializes the service
        """
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.exaile = exaile


    @dbus.service.method("org.exaile.DBusInterface")
    def play_file(self, f):
        """
            Plays the specified file
        """
        if f.endswith(".m3u") or f.endswith(".pls"):
            self.exaile.import_m3u(f, True)
        else: self.exaile.stream(f)


    @dbus.service.method("org.exaile.DBusInterface")
    def test_service(self, arg):
        """
            Just a method to test the service
        """
        print arg


    @dbus.service.method("org.exaile.DBusInterface")
    def prev_track(self):
        """
            Jumps to the previous track
        """
        self.exaile.on_previous()


    @dbus.service.method("org.exaile.DBusInterface")
    def stop(self):
        """
            Stops playback
        """
        self.exaile.stop()


    @dbus.service.method("org.exaile.DBusInterface")
    def next_track(self):
        """
            Jumps to the next track
        """
        self.exaile.on_next()


    @dbus.service.method("org.exaile.DBusInterface")
    def play(self):
        """
            Starts playback
        """
        self.exaile.play()


    @dbus.service.method("org.exaile.DBusInterface")
    def query(self):
        """
            Returns information about the currently playing track
        """
        if not self.exaile.current_track:
            return "No track playing"
        return self.exaile.current_track.full_status()

    @dbus.service.method("org.exaile.DBusInterface")
    def popup(self):
        """
            Shows a popup window with information about the current track
        """
        self.exaile.show_popup()
