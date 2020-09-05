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

"""
    D-Bus interface for playback control, data query and others

    Access through the ``/org/exaile/Exaile`` object which
    implements the ``org.exaile.Exaile`` interface
"""

from collections import namedtuple
import logging
import sys

import dbus
import dbus.service
from gi.repository import Gio

# Be VERY careful what you import here! This module gets loaded even if
# we are just issuing a dbus command to a running instance, so we need
# to keep imports as light as possible.
from xl import event
from xl.nls import gettext as _

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
    iface = None
    if not options.NewInstance:
        # TODO: handle dbus stuff
        bus = dbus.SessionBus()
        if check_dbus(bus, 'org.exaile.Exaile'):
            remote_object = bus.get_object('org.exaile.Exaile', '/org/exaile/Exaile')
            iface = dbus.Interface(remote_object, 'org.exaile.Exaile')
            iface.TestService('testing dbus service')

            # Assume that args are files to be added to the current playlist.
            # This enables:    exaile PATH/*.mp3
            if args:
                # if '-' is the first argument then we look for a newline
                # separated list of filenames from stdin.
                # This enables:    find PATH -name *.mp3 | exaile -
                if args[0] == '-':
                    args = sys.stdin.read().split('\n')
                args = [Gio.File.new_for_commandline_arg(arg).get_uri() for arg in args]
                iface.Enqueue(args)

    if not iface:
        for command in [
            'GetArtist',
            'GetTitle',
            'GetAlbum',
            'GetLength',
            'GetRating',
            'SetRating',
            'IncreaseVolume',
            'DecreaseVolume',
            'Play',
            'Pause',
            'Stop',
            'Next',
            'Prev',
            'PlayPause',
            'StopAfterCurrent',
            'GuiToggleVisible',
            'CurrentPosition',
            'CurrentProgress',
            'GetVolume',
            'Query',
            'FormatQuery',
        ]:
            if getattr(options, command):
                return "command"
        return "continue"

    run_commands(options, iface)
    return "exit"


def run_commands(options, iface):
    """
    Actually invoke any commands passed in.
    """
    comm = False
    info_commands = {
        'GetArtist': 'artist',
        'GetTitle': 'title',
        'GetAlbum': 'album',
        'GetLength': '__length',
    }

    for command, attr in info_commands.items():
        if getattr(options, command):
            value = iface.GetTrackAttr(attr)
            if value is None:
                print(_('Not playing.'))
            else:
                print(value)
            comm = True

    argument_commands = (
        'IncreaseVolume',
        'DecreaseVolume',
        'SetRating',
        'Add',
        'ExportPlaylist',
    )

    for command in argument_commands:
        argument = getattr(options, command)
        if argument is not None:
            if command in ('IncreaseVolume', 'DecreaseVolume'):
                iface.ChangeVolume(
                    argument if command == 'IncreaseVolume' else -argument
                )
            else:
                print(getattr(iface, command)(argument))

            comm = True

    # Special handling for FormatQuery & FormatQueryTags
    format = options.FormatQuery
    if format is not None:
        print(
            iface.FormatQuery(
                format, options.FormatQueryTags or 'title,artist,album,__length'
            )
        )
        comm = True

    run_commands = (
        'Play',
        'Pause',
        'Stop',
        'Next',
        'Prev',
        'PlayPause',
        'StopAfterCurrent',
        'GuiToggleVisible',
        'ToggleMute',
    )

    for command in run_commands:
        if getattr(options, command):
            getattr(iface, command)()
            comm = True

    query_commands = (
        'CurrentPosition',
        'CurrentProgress',
        'GetRating',
        'GetVolume',
        'Query',
    )

    for command in query_commands:
        if getattr(options, command):
            print(getattr(iface, command)(argument))
            comm = True

    to_implement = ('GuiQuery',)
    for command in to_implement:
        if getattr(options, command):
            logger.warning("FIXME: command not implemented")
            comm = True

    if not comm:
        iface.GuiToggleVisible()


PlaybackStatus = namedtuple('PlaybackStatus', 'state progress position current')


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
        self.bus_name = dbus.service.BusName('org.exaile.Exaile', bus=self.bus)
        dbus.service.Object.__init__(self, self.bus_name, '/org/exaile/Exaile')
        self.cached_track = ""
        self.cached_state = ""
        self.cached_volume = -1

    def _connect_signals(self):
        # connect events
        from xl import player

        event.add_callback(
            self.emit_state_changed, 'playback_player_end', player.PLAYER
        )
        event.add_callback(
            self.emit_state_changed, 'playback_track_start', player.PLAYER
        )
        event.add_callback(
            self.emit_state_changed, 'playback_toggle_pause', player.PLAYER
        )
        event.add_callback(self.emit_track_changed, 'tags_parsed', player.PLAYER)
        event.add_callback(self.emit_state_changed, 'playback_buffering', player.PLAYER)
        event.add_callback(self.emit_state_changed, 'playback_error', player.PLAYER)

    @dbus.service.method('org.exaile.Exaile', 's')
    def TestService(self, arg):
        """
        Just test the dbus object

        :param arg: anything
        """
        logger.debug(arg)

    @dbus.service.method('org.exaile.Exaile', None, 'b')
    def IsPlaying(self):
        """
        Determines if Exaile is playing / paused or not

        :returns: whether Exaile is playing / paused
        :rtype: boolean
        """
        from xl import player

        return bool(not player.PLAYER.is_stopped())

    @dbus.service.method('org.exaile.Exaile', 's', 's')
    def GetTrackAttr(self, attr):
        """
        Returns the value of a track tag

        :param attr: a track tag
        :type attr: string
        :returns: the tag value
        :rtype: string
        """
        from xl import player

        try:
            value = player.PLAYER.current.get_tag_raw(attr) or ''
        except (ValueError, TypeError, AttributeError):
            value = ''

        if isinstance(value, list):
            return "\n".join(value)
        return str(value)

    @dbus.service.method('org.exaile.Exaile', 'sv')
    def SetTrackAttr(self, attr, value):
        """
        Sets the value of a track tag

        :param attr: a track tag
        :type attr: string
        :param value: the tag value
        :type value: any
        """
        from xl import player

        try:
            player.PLAYER.current.set_tag_raw(attr, value)
        except (AttributeError, TypeError):
            pass

    @dbus.service.method('org.exaile.Exaile', None, 'i')
    def GetRating(self):
        """
        Returns the current track's rating

        :returns: the rating
        :rtype: int
        """
        try:
            rating = int(float(self.GetTrackAttr('__rating')))
        except ValueError:
            rating = 0

        return rating

    @dbus.service.method('org.exaile.Exaile', 'i')
    def SetRating(self, value):
        """
        Sets the current track's rating

        :param value: the new rating
        :type value: int
        """
        self.SetTrackAttr('__rating', value)
        event.log_event('rating_changed', self, value)

    @dbus.service.method('org.exaile.Exaile', 'i')
    def ChangeVolume(self, value):
        """
        Changes volume by the specified amount (in percent, can be negative)

        :param value: the new volume
        :type value: int
        """
        from xl import player

        player.PLAYER.set_volume(player.PLAYER.get_volume() + value)
        self.cached_volume = -1

    @dbus.service.method('org.exaile.Exaile')
    def ToggleMute(self):
        """
        Mutes or unmutes the volume
        """
        from xl import player

        if self.cached_volume == -1:
            self.cached_volume = player.PLAYER.get_volume()
            player.PLAYER.set_volume(0)
        else:
            player.PLAYER.set_volume(self.cached_volume)
            self.cached_volume = -1

    @dbus.service.method('org.exaile.Exaile', 'd')
    def Seek(self, value):
        """
        Seeks to the given position in seconds

        :param value: the position in seconds
        :type value: int
        """
        from xl import player

        player.PLAYER.seek(value)

    @dbus.service.method('org.exaile.Exaile')
    def Prev(self):
        """
        Jumps to the previous track
        """
        from xl import player

        player.QUEUE.prev()

    @dbus.service.method('org.exaile.Exaile')
    def Stop(self):
        """
        Stops playback
        """
        from xl import player

        player.PLAYER.stop()

    @dbus.service.method('org.exaile.Exaile')
    def Next(self):
        """
        Jumps to the next track
        """
        from xl import player

        player.QUEUE.next()

    @dbus.service.method('org.exaile.Exaile')
    def Play(self):
        """
        Starts playback
        """
        from xl import player

        player.QUEUE.play()

    @dbus.service.method('org.exaile.Exaile')
    def Pause(self):
        """
        Starts playback
        """
        from xl import player

        player.PLAYER.pause()

    @dbus.service.method('org.exaile.Exaile')
    def PlayPause(self):
        """
        Toggle Play or Pause
        """
        from xl import player

        if player.PLAYER.is_stopped():
            player.PLAYER.play(player.QUEUE.get_current())
        else:
            player.PLAYER.toggle_pause()

    @dbus.service.method('org.exaile.Exaile')
    def StopAfterCurrent(self):
        """
        Toggle stopping after current track
        """
        from xl import player

        player.QUEUE.stop_track = player.QUEUE.get_current()

    @dbus.service.method('org.exaile.Exaile', None, 's')
    def CurrentProgress(self):
        """
        Returns the progress into the current track (in percent)

        :returns: the current progress
        :rtype: string
        """
        from xl import player

        progress = player.PLAYER.get_progress()
        if progress == -1:
            return ""
        return str(int(progress * 100))

    @dbus.service.method('org.exaile.Exaile', None, 's')
    def CurrentPosition(self):
        """
        Returns the position inside the current track (as time)

        :returns: the current position
        :rtype: string
        """
        from xl import player

        progress = player.PLAYER.get_time()
        return '%d:%02d' % (progress // 60, progress % 60)

    @dbus.service.method('org.exaile.Exaile', None, 's')
    def GetVolume(self):
        """
        Returns the current volume level (in percent)

        :returns: the current volume
        :rtype: string
        """
        from xl import player

        return str(player.PLAYER.get_volume())

    def __get_playback_status(self, tags=["title", "artist", "album", "__length"]):
        """
        Retrieves the playback status

        :param tags: tags to retrieve from the current track
        :type tags: list
        :returns: the playback status
        :rtype: :class:`xl.xldbus.PlaybackStatus`
        """
        status = PlaybackStatus(state='stopped', current=None, progress=0, position=0)

        from xl import player

        current_track = player.QUEUE.get_current()
        if current_track is not None and not player.PLAYER.is_stopped():
            current = {}
            # Make tags unique
            tags = list(set(tags))

            for tag in tags:
                current[tag] = self.GetTrackAttr(tag)

            # Special handling for internal tags
            if "__length" in tags:
                from xl.formatter import LengthTagFormatter

                current["__length"] = LengthTagFormatter.format_value(
                    self.GetTrackAttr('__length')
                )

            status = PlaybackStatus(
                state=player.PLAYER.get_state(),
                progress=self.CurrentProgress(),
                position=self.CurrentPosition(),
                current=current,
            )

        return status

    @dbus.service.method('org.exaile.Exaile', None, 's')
    def Query(self):
        """
        Returns information about the currently playing track

        :returns: information about the current track
        :rtype: string
        """
        status = self.__get_playback_status()

        if status.current is None or status.state == "stopped":
            return _('Not playing.')

        result = _(
            'status: %(status)s, title: %(title)s, artist: %(artist)s,'
            ' album: %(album)s, length: %(length)s,'
            ' position: %(progress)s%% [%(position)s]'
        ) % {
            'status': status.state,
            'title': status.current["title"],
            'artist': status.current["artist"],
            'album': status.current["album"],
            'length': status.current["__length"],
            'progress': status.progress,
            'position': status.position,
        }

        return result

    @dbus.service.method('org.exaile.Exaile', 'ss', 's')
    def FormatQuery(self, format, tags):
        """
        Returns the current playback state including
        information about the currently playing track

        :param format: the desired output format (currently only "json")
        :type format: string
        :param tags: tags to retrieve from the current track
        :type tags: string
        :returns: the formatted information or an empty
                  string if requesting an unknown format
        :rtype: string
        """
        # TODO: Elaborate the use of providers here
        if format == 'json':
            import json

            status = self.__get_playback_status(tags.split(","))

            return json.dumps(status._asdict())

        return ''

    @dbus.service.method('org.exaile.Exaile', None, 's')
    def GetVersion(self):
        """
        Returns the version of Exaile

        :returns: the application version
        :rtype: string
        """
        return self.exaile.get_version()

    @dbus.service.method('org.exaile.Exaile', 's')
    def PlayFile(self, filename):
        """
        Plays the specified file

        :param filename: the path to start playing
        :type filename: string
        """
        self.exaile.gui.open_uri(filename)

    @dbus.service.method('org.exaile.Exaile', 'as')
    def Enqueue(self, locations):
        """
        Adds the tracks at the specified locations
        to the current playlist

        :param locations: locations to enqueue
        :type locations: iterable
        """
        from xl import player
        from xlgui import get_controller

        controller = get_controller()

        play = False

        # Allows for playing first item
        if player.PLAYER.is_stopped():
            play = True

        for location in locations:
            controller.open_uri(location, play=play)
            play = False

    @dbus.service.method('org.exaile.Exaile', 's')
    def Add(self, location):
        """
        Adds the tracks at the specified
        location to the collection

        :param location: where to add tracks from
        :type location: string
        """
        from xl import trax

        tracks = trax.get_tracks_from_uri(location)
        self.exaile.collection.add_tracks(tracks)

    @dbus.service.method('org.exaile.Exaile', 's')
    def ExportPlaylist(self, location):
        """
        Exports the current playlist
        to the specified location

        :param location: where to save the playlist at
        :type location: string
        """
        from xl import player, playlist

        if player.QUEUE.current_playlist is not None:
            playlist.export_playlist(player.QUEUE.current_playlist, location)

    @dbus.service.method('org.exaile.Exaile')
    def GuiToggleVisible(self):
        """
        Toggles visibility of the GUI, if possible
        """
        self.exaile.gui.main.toggle_visible(bringtofront=True)

    @dbus.service.method('org.exaile.Exaile', None, 'ay')
    def GetCoverData(self):
        """
        Returns the data of the cover image of the playing track, or
        an empty string if there is no cover available.

        :returns: the cover data
        :rtype: binary data
        """
        from xl import covers, player

        cover = covers.MANAGER.get_cover(player.PLAYER.current, set_only=True)
        if not cover:
            cover = ''
        return cover

    @dbus.service.method('org.exaile.Exaile', None, 's')
    def GetState(self):
        """
        Returns the surrent verbatim state (unlocalized)

        :returns: the player state
        :rtype: string
        """
        from xl import player

        return player.PLAYER.get_state()

    @dbus.service.signal('org.exaile.Exaile')
    def StateChanged(self):
        """
        Emitted when state change occurs: 'playing' 'paused' 'stopped'
        """
        pass

    @dbus.service.signal('org.exaile.Exaile')
    def TrackChanged(self):
        """
        Emitted when track change occurs.
        """
        pass

    def emit_state_changed(self, type, player, object):
        """
        Called from main to emit signal
        """
        new_state = player.get_state()
        if self.cached_state != new_state:
            self.cached_state = new_state
            self.StateChanged()

    def emit_track_changed(self, type, player, object):
        """
        Called from main to emit signal
        """
        new_track = self.GetTrackAttr('__loc')
        if self.cached_track != new_track:
            self.cached_track = new_track
            self.TrackChanged()


# vim: et sts=4 sw=4
