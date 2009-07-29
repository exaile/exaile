# Copyright (C) 2008-2009 Adam Olsen 
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

from xl.nls import gettext as _
import logging
import dbus, dbus.service, gobject, sys, os
from optparse import OptionParser

logger = logging.getLogger(__name__)

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
    iface = False
    exaile = None
    if not options.NewInstance:
        # TODO: handle dbus stuff
        bus = dbus.SessionBus()
        if check_dbus(bus, 'org.exaile.Exaile'):
            remote_object = bus.get_object('org.exaile.Exaile', 
                '/org/exaile/Exaile')
            iface = dbus.Interface(remote_object, 'org.exaile.Exaile')
            iface.TestService('testing dbus service')
            exaile = remote_object.exaile

            # Assume that args are files to be added to the current playlist.
            # This enables:    exaile PATH/*.mp3
            if args:
                # if '-' is the first argument then we look for a newline 
                # separated list of filenames from stdin.
                # This enables:    find PATH -name *.mp3 | exaile -
                if args[0] == '-':
                    args = sys.stdin.read().split('\n')
                args = [ os.path.abspath(arg) for arg in args ]
                print args
                iface.Enqueue(args)
            
    if not iface:
        return False

    comm = False
    info_commands = {
            'GetArtist': 'artist', 
            'GetTitle': 'title', 
            'GetAlbum': 'album',
            'GetLength': '__length', 
            'GetRating': 'rating',
            }

    for command, attr in info_commands.iteritems():
        if getattr(options, command):
            value = iface.GetTrackAttr(attr)
            if value is None:
                print _('Not playing.')
            else:
                print value
            comm = True

    modify_commands = (
           'SetRating',
           )

    for command in modify_commands:
        value = getattr(options, command)
        if value:
            iface.SetTrackAttr(command[4:].lower(), value)
            comm = True

    volume_commands = (
            'IncreaseVolume',
            'DecreaseVolume',
            )

    for command in volume_commands:
        value = getattr(options, command)
        if value:
            if command == 'DecreaseVolume': value = -value
            iface.ChangeVolume(value)

    run_commands = (
            'Play', 
            'Stop', 
            'Next', 
            'Prev', 
            'PlayPause',
            'StopAfterCurrent'
            )
    for command in run_commands:
        if getattr(options, command):
            getattr(iface, command)()
            comm = True

    query_commands = (
            'CurrentPosition',
            'CurrentProgress',
            'GetVolume',
            'Query',
            )

    for command in query_commands:
        if getattr(options, command):
            print getattr(iface, command)()
            comm = True

    to_implement = (
            'GuiQuery',
            )
    for command in to_implement:
        if getattr(options, command):
            logger.warning("FIXME: command not implemented")
            comm = True

    return True

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
        self.bus_name = dbus.service.BusName('org.exaile.Exaile',
            bus=self.bus)
        dbus.service.Object.__init__(self, self.bus_name, "/org/exaile/Exaile")

    @dbus.service.method('org.exaile.Exaile', 's')
    def TestService(self, arg):
        """
            Just test the dbus object
        """
        logger.debug(arg)

    @dbus.service.method('org.exaile.Exaile', None, 'b')
    def IsPlaying(self):
        """
            Returns True if Exaile is playing (or paused), False if it's not
        """
        return bool(self.exaile.player.current)

    @dbus.service.method('org.exaile.Exaile', 's')
    def GetTrackAttr(self, attr):
        """
            Returns a attribute of a track
        """
        try:
            value = self.exaile.player.current[attr]
        except ValueError:
            value = None
        except TypeError:
            value = None

        if value:
            if type(value) == list:
                return u"\n".join(value)
            return unicode(value)
        return value

    @dbus.service.method("org.exaile.Exaile", 'sv')
    def SetTrackAttr(self, attr, value):
        """
            Sets rating of a track
        """
        try:
            set_attr = getattr(self.exaile.player.current, attr)
            set_attr(value)
        except AttributeError:
            pass
        except TypeError:
            pass

    @dbus.service.method("org.exaile.Exaile", 'i')
    def ChangeVolume(self, value):
        """
            Changes volume by the specified amount (in percent, can be negative)
        """
        player = self.exaile.player
        player.set_volume(player.get_volume() + value)

    @dbus.service.method("org.exaile.Exaile")
    def Prev(self):
        """
            Jumps to the previous track
        """
        self.exaile.queue.prev()

    @dbus.service.method("org.exaile.Exaile")
    def Stop(self):
        """
            Stops playback
        """
        self.exaile.player.stop()

    @dbus.service.method("org.exaile.Exaile")
    def Next(self):
        """
            Jumps to the next track
        """
        self.exaile.queue.next()

    @dbus.service.method("org.exaile.Exaile")
    def Play(self):
        """
            Starts playback
        """
        self.exaile.queue.play()

    @dbus.service.method("org.exaile.Exaile")
    def PlayPause(self):
        """
            Toggle Play or Pause
        """
        self.exaile.player.toggle_pause()

    @dbus.service.method("org.exaile.Exaile")
    def StopAfterCurrent(self):
        """
            Toggle stopping after current track
        """
        current_track = self.exaile.queue.get_current()
        self.exaile.queue.stop_track = current_track

    @dbus.service.method("org.exaile.Exaile", None, "s")
    def CurrentProgress(self):
        """
            Returns the progress into the current track (in percent)
        """
        progress = self.exaile.player.get_progress()
        if progress == -1:
            return ""
        return str(int(progress * 100))

    @dbus.service.method("org.exaile.Exaile", None, "s")
    def CurrentPosition(self):
        """
            Returns the position inside the current track (as time)
        """
        progress = self.exaile.player.get_progress()
        if progress == -1:
            return ''
        length = float(self.GetTrackAttr('__length'))
        progress = length * progress

        return '%d:%02d' % (progress // 60, progress % 60)

    @dbus.service.method("org.exaile.Exaile", None, "s")
    def GetVolume(self):
        """
            Returns the current volume level (in percent)
        """
        return str(self.exaile.player.get_volume())

    @dbus.service.method("org.exaile.Exaile", None, "s")
    def Query(self):
        """
            Returns information about the currently playing track
        """
        current_track = self.exaile.queue.get_current()
        if current_track is None or not \
           (self.exaile.player.is_playing() or self.exaile.player.is_paused()):
            return _('Not playing.')

        length = float(self.GetTrackAttr('__length'))
        length = '%d:%02d' % (length // 60, length % 60)

        result = _('status: %(status)s, title: %(title)s, artist: %(artist)s,'
                   ' album: %(album)s, length: %(length)s,'
                   ' position: %(progress)s%% [%(position)s]') % {
                         'status': self.exaile.player.get_state(),
                         'title': self.GetTrackAttr('title'),
                         'artist': self.GetTrackAttr('artist'),
                         'album': self.GetTrackAttr('album'),
                         'length': length,
                         'progress': self.CurrentProgress(),
                         'position': self.CurrentPosition(),
                     }

        return result

    @dbus.service.method("org.exaile.Exaile", None, "s")
    def GetVersion(self):
        """
            Returns the version of Exaile
        """
        return self.exaile.get_version()

    @dbus.service.method("org.exaile.Exaile", "s")
    def PlayFile(self, filename):
        """
            Plays the specified file
        """
        self.exaile.gui.open_uri(filename)

    @dbus.service.method("org.exaile.Exaile", "as")
    def Enqueue(self, filenames):
        """
            Adds the specified files to the current playlist
        """
        import xl.playlist
        from xl import track  # do this here to avoid loading 
                              # settings when issuing dbus commands
        # FIXME: Get rid of dependency on xlgui
        #        by moving sorting column somewhere else
        pl = self.exaile.gui.main.get_selected_playlist()
        column, descending = pl.get_sort_by()
        tracks = []
        playlists = []

        for file in filenames:
            try:
                pl = xl.playlist.import_playlist(file)
                tracks = pl.get_tracks()
                continue
            except xl.playlist.InvalidPlaylistTypeException:
                pass
            except:
                traceback.print_exc()
                
            tracks += track.get_tracks_from_uri(file)

        print tracks
        print [t._scan_valid for t in tracks]

        tracks.sort(key=lambda track: track.sort_param(column), reverse=descending)
        self.exaile.queue.current_playlist.add_tracks(tracks)

        if not self.exaile.player.is_playing():
            try:
                pos = self.exaile.queue.current_playlist.index(tracks[0])
                self.exaile.queue.current_playlist.set_current_pos(pos)
                self.exaile.queue.play()
            except IndexError:
                pass
