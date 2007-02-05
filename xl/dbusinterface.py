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

import sys, traceback
import dbus
import dbus.service
import dbus.glib

dbus.glib.threads_init()
import gobject
from optparse import OptionParser

options = None

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
    def play_pause(self):
        """
            Toggle Play or Pause
        """
        self.exaile.toggle_pause()

    @dbus.service.method("org.exaile.DBusInterface")
    def query(self):
        """
            Returns information about the currently playing track
        """
        if not self.exaile.player.current:
            return "No track playing"
        return self.exaile.player.current.full_status()

    @dbus.service.method("org.exaile.DBusInterface")
    def popup(self):
        """
            Shows a popup window with information about the current track
        """
        self.exaile.show_osd()

    @dbus.service.method("org.exaile.DBusInterface")
    def get_title(self):
        """
            Returns the title of the playing track
        """
        if not self.exaile.player.current:
            return ""
        return self.exaile.player.current.get_title()

    @dbus.service.method("org.exaile.DBusInterface")
    def get_album(self):
        """
            Returns the album of the playing track
        """
        if not self.exaile.player.current:
            return ""
        return self.exaile.player.current.album

    @dbus.service.method("org.exaile.DBusInterface")
    def get_artist(self):
        """
            Returns the artist of the playing track
        """
        if not self.exaile.player.current:
            return ""
        return self.exaile.player.current.artist

    @dbus.service.method("org.exaile.DBusInterface")
    def get_length(self):
        """
            Returns the length of the playing track
        """
        if not self.exaile.player.current:
            return ""
        return self.exaile.player.current.length


    @dbus.service.method("org.exaile.DBusInterface")
    def current_position(self):
        """
            Returns the position inside the current track as a percentage
        """
        if not self.exaile.player.current:
            return 0
        return self.exaile.player.get_current_position()

    @dbus.service.method("org.exaile.DBusInterface")
    def status(self):
        """
            Returns if the player is paused or playing
        """
        if not self.exaile.player.current:
            return "No track playing"
        return self.exaile.player.current.status()

    @dbus.service.method("org.exaile.DBusInterface")
    def get_cover_path(self):
        """
            Returns the path to the cover image of the playing track
        """
        return self.exaile.cover.loc

    @dbus.service.method("org.exaile.DBusInterface")
    def popup(self):
        """
            Shows a popup window with information about the current track
        """
        self.exaile.show_osd()

    @dbus.service.method("org.exaile.DBusInterface")
    def increase_volume(self,vol):
        """ 
            Increases the volume by vol
        """
        vol = vol + self.exaile.volume.get_value()
        self.exaile.volume.set_value(vol)

    @dbus.service.method("org.exaile.DBusInterface")
    def decrease_volume(self,vol):
        """ 
            dereases the volume by vol
        """
        vol = self.exaile.volume.get_value() - vol
        self.exaile.volume.set_value(vol)

    @dbus.service.method("org.exaile.DBusInterface")
    def toggle_visibility(self):
        """
            Toggle the main window's visibility
        """
        if not self.exaile.window.get_property('visible'):
            self.exaile.window.show_all()
            self.exaile.setup_location()
        else:
           self.exaile.window.hide()

    @dbus.service.method("org.exaile.DBusInterface")
    def get_version(self):
        return self.exaile.get_version()


def test_dbus(bus, interface):
    obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus') 
    dbus_iface = dbus.Interface(obj, 'org.freedesktop.DBus') 
    avail = dbus_iface.ListNames() 
    return interface in avail

def test(p):
    """
        Tests to see if the dbus service is running, and if it is, call
        methods on the service
    """

    global options
    (options, args) = p.parse_args()
    if not options.new:
        try:
            bus = dbus.SessionBus()
            if test_dbus(bus, 'org.exaile.DBusInterface'):
                remote_object = bus.get_object("org.exaile.DBusInterface",
                    "/DBusInterfaceObject")
                iface = dbus.Interface(remote_object, "org.exaile.DBusInterface")
                iface.test_service("testing dbus service")
                if options.next: iface.next_track()
                elif options.prev: iface.prev_track()
                elif options.stop: iface.stop()
                elif options.play: iface.play()
                elif options.play_pause: iface.play_pause()
                elif options.guiquery: iface.popup()
                elif options.stream: iface.play_file(options.stream)

                do_exit = False
                if options.get_title:
                    print iface.get_title()
                    do_exit = True
                if options.get_artist:
                    print iface.get_artist()
                    do_exit = True
                if options.get_album:
                    print iface.get_album()
                    do_exit = True
                if options.show_version:
                    print iface.get_version()
                    do_exit = True
                    sys.exit(0)
                if options.get_length:
                    print iface.get_length()
                    do_exit = True
                if options.current_position:
                    print iface.current_position()
                    do_exit = True
                if options.inc_vol:
                    iface.increase_volume(options.inc_vol)
                elif options.dec_vol:
                    iface.decrease_volume(options.dec_vol)
                elif options.query:

                    print iface.query()
                    #if track == None: print "status: stopped"
                    #else: print track.full_status()
                elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
                    iface.play_file(sys.argv[1])
                elif not do_exit:
                    iface.toggle_visibility()
                    print "You have entered an invalid option"
                return True
        except SystemExit:
            return True
        except:
            traceback.print_exc()
            True

    return False

def get_options():
    """
        Get the options for exaile
    """
    usage = "usage: %prog [options]"
    p = OptionParser(usage=usage)
    p.add_option("-d", "--duplicates", dest="dups",
        metavar="DIR",
        help="Finds and deletes all duplicate tracks (based on their md5 sum)")
    p.add_option("-n", "--next", dest="next", action="store_true",
        default=False, help="Play the next track")
    p.add_option("-p", "--prev", dest="prev", action="store_true",
        default=False,   help="Play the previous track")
    p.add_option("-s", "--stop", dest="stop", action="store_true",
        default=False, help="Stop playback")
    p.add_option("-a", "--play", dest="play", action="store_true",
        default=False, help="Play")
    p.add_option("-t", "--play-pause", dest="play_pause", action="store_true",
        default=False, help="Toggle Play or Pause")
    p.add_option("-q", "--query", dest="query", action="store_true",
        default=False, help="Query player")
    p.add_option("--gui-query", dest="guiquery", action="store_true",
        default=False, help="Show a popup of the currently playing track")
    p.add_option("--get-title", dest="get_title", action="store_true",
        default=False, help="Print the title of current track")
    p.add_option("--get-album", dest="get_album", action="store_true",
        default=False, help="Print the album of current track")
    p.add_option("--get-artist", dest="get_artist", action="store_true",
        default=False, help="Print the artist of current track")
    p.add_option("--get-length", dest="get_length", action="store_true",
        default=False, help="Print the length of current track")
    p.add_option("--current-position", dest="current_position", action="store_true",
        default=False, help="Print the position inside the current track as a percentage")
    p.add_option("-i","--increase_vol", dest="inc_vol",action="store", 
        type="int",metavar="VOL",help="Increases the volume by VOL")
    p.add_option("-l","--decrease_vol", dest="dec_vol",action="store",
        type="int",metavar="VOL",help="Decreases the volume by VOL")
    p.add_option("--stream", dest="stream", help="Stream URL")
    p.add_option("--new", dest="new", action="store_true",
        default=False, help="Start new instance")
    p.add_option("--settings", dest="settings", help="Settings Directory")
    p.add_option("--cleanversion", dest="cleanversion", action="store_true")
    p.add_option("--version", dest="show_version", action="store_true")
    p.add_option("--testing", dest="testing", action="store_true")

    return p
