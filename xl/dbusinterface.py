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

    @dbus.service.method("org.exaile.DBusInterface")
    def get_title(self):
        """
            Returns the title of the playing track
        """
        if not self.exaile.current_track:
            return ""
        return self.exaile.current_track.get_title()

    @dbus.service.method("org.exaile.DBusInterface")
    def get_album(self):
        """
            Returns the album of the playing track
        """
        if not self.exaile.current_track:
            return ""
        return self.exaile.current_track.album

    @dbus.service.method("org.exaile.DBusInterface")
    def get_artist(self):
        """
            Returns the artist of the playing track
        """
        if not self.exaile.current_track:
            return ""
        return self.exaile.current_track.artist

    @dbus.service.method("org.exaile.DBusInterface")
    def get_length(self):
        """
            Returns the length of the playing track
        """
        if not self.exaile.current_track:
            return ""
        return self.exaile.current_track.length


    @dbus.service.method("org.exaile.DBusInterface")
    def current_position(self):
        """
            Returns the position inside the current track as a percentage
        """
        if not self.exaile.current_track:
            return 0
        return self.exaile.current_track.current_position()

    @dbus.service.method("org.exaile.DBusInterface")
    def status(self):
        """
            Returns if the player is paused or playing
        """
        if not self.exaile.current_track:
            return "No track playing"
        return self.exaile.current_track.status()

    @dbus.service.method("org.exaile.DBusInterface")
    def popup(self):
        """
            Shows a popup window with information about the current track
        """
        self.exaile.show_popup()

    @dbus.service.method("org.exaile.DBusInterface")
    def increase_volume(self,vol):
        """ 
            Increases the volume by vol
        """
        vol = vol + self.exaile.volume.slider.get_value()
        self.exaile.volume.slider.set_value(vol)
        self.exaile.on_volume_set()

    @dbus.service.method("org.exaile.DBusInterface")
    def decrease_volume(self,vol):
        """ 
            dereases the volume by vol
        """
        vol = self.exaile.volume.slider.get_value() - vol
        self.exaile.volume.slider.set_value(vol)
        self.exaile.on_volume_set()

