# Copyright (C) 2009-2010 Abhishek Mukherjee
#
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
"""/Player object for MPRIS specification interface to Exaile

http://wiki.xmms2.xmms.se/wiki/MPRIS#.2FPlayer_object_methods
"""


from __future__ import division

from xl import player, settings

import dbus
import dbus.service

import xl.event

import mpris_tag_converter

INTERFACE_NAME = 'org.freedesktop.MediaPlayer'

class MprisCaps(object):
    """
        Specification for the capabilities field in MPRIS
    """
    NONE                  = 0
    CAN_GO_NEXT           = 1 << 0
    CAN_GO_PREV           = 1 << 1
    CAN_PAUSE             = 1 << 2
    CAN_PLAY              = 1 << 3
    CAN_SEEK              = 1 << 4
    CAN_PROVIDE_METADATA  = 1 << 5
    CAN_HAS_TRACKLIST     = 1 << 6

EXAILE_CAPS = (MprisCaps.CAN_GO_NEXT
                | MprisCaps.CAN_GO_PREV
                | MprisCaps.CAN_PAUSE
                | MprisCaps.CAN_PLAY
                | MprisCaps.CAN_SEEK
                | MprisCaps.CAN_PROVIDE_METADATA
                | MprisCaps.CAN_HAS_TRACKLIST)

class ExaileMprisPlayer(dbus.service.Object):

    """
        /Player (Root) object methods
    """

    def __init__(self, exaile, bus):
        dbus.service.Object.__init__(self, bus, '/Player')
        self.exaile = exaile
        self._tag_converter = mpris_tag_converter.ExaileTagConverter(exaile)
        xl.event.add_callback(self.track_change_cb, 'playback_track_start')
        # FIXME: Does not watch for shuffle, repeat
        # TODO: playback_start does not distinguish if play button was pressed
        #       or we simply moved to a new track
        for event in ('playback_player_end', 'playback_player_start',
                'playback_toggle_pause'):
            xl.event.add_callback(self.status_change_cb, event)


    @dbus.service.method(INTERFACE_NAME)
    def Next(self):
        """
            Goes to the next element
        """
        player.QUEUE.next()

    @dbus.service.method(INTERFACE_NAME)
    def Prev(self):
        """
            Goes to the previous element
        """
        player.QUEUE.prev()

    @dbus.service.method(INTERFACE_NAME)
    def Pause(self):
        """
            If playing, pause. If paused, unpause.
        """
        player.PLAYER.toggle_pause()

    @dbus.service.method(INTERFACE_NAME)
    def Stop(self):
        """
            Stop playing
        """
        player.PLAYER.stop()

    @dbus.service.method(INTERFACE_NAME)
    def Play(self):
        """
            If Playing, rewind to the beginning of the current track, else.
            start playing
        """
        if player.PLAYER.is_playing():
            player.PLAYER.play(player.PLAYER.current)
        else:
            player.QUEUE.play()

    @dbus.service.method(INTERFACE_NAME, in_signature="b")
    def Repeat(self, repeat):
        """
            Toggle the current track repeat
        """
        pass

    @dbus.service.method(INTERFACE_NAME, out_signature="(iiii)")
    def GetStatus(self):
        """
            Return the status of "Media Player" as a struct of 4 ints:
              * First integer: 0 = Playing, 1 = Paused, 2 = Stopped.
              * Second interger: 0 = Playing linearly , 1 = Playing randomly.
              * Third integer: 0 = Go to the next element once the current has
                finished playing , 1 = Repeat the current element
              * Fourth integer: 0 = Stop playing once the last element has been
                played, 1 = Never give up playing
        """
        if player.PLAYER.is_playing():
            playing = 0
        elif player.PLAYER.is_paused():
            playing = 1
        else:
            playing = 2

        if player.QUEUE.current_playlist.get_shuffle_mode() == 'disabled':
            random = 0
        else:
            random = 1

        if player.QUEUE.current_playlist.get_repeat_mode() == 'track':
            go_to_next = 0
        else:
            go_to_next = 1

        if player.QUEUE.current_playlist.get_repeat_mode() == 'all':
            repeat = 1
        else:
            repeat = 0

        return (playing, random, go_to_next, repeat)

    @dbus.service.method(INTERFACE_NAME, out_signature="a{sv}")
    def GetMetadata(self):
        """
            Gives all meta data available for the currently played element.
        """
        if player.PLAYER.current is None:
            return []
        return self._tag_converter.get_metadata(player.PLAYER.current)

    @dbus.service.method(INTERFACE_NAME, out_signature="i")
    def GetCaps(self):
        """
            Returns the "Media player"'s current capabilities, see MprisCaps
        """
        return EXAILE_CAPS

    @dbus.service.method(INTERFACE_NAME, in_signature="i")
    def VolumeSet(self, volume):
        """
            Sets the volume, arument in the range [0, 100]
        """
        if volume < 0 or volume > 100:
            pass

        settings.set_option('player/volume', volume / 100)

    @dbus.service.method(INTERFACE_NAME, out_signature="i")
    def VolumeGet(self):
        """
            Returns the current volume (must be in [0;100])
        """
        return settings.get_option('player/volume', 0) * 100

    @dbus.service.method(INTERFACE_NAME, in_signature="i")
    def PositionSet(self, millisec):
        """
            Sets the playing position (argument must be in [0, <track_length>]
            in milliseconds)
        """
        if millisec > player.PLAYER.current.get_tag_raw('__length') \
                * 1000 or millisec < 0:
            return
        player.PLAYER.seek(millisec / 1000)

    @dbus.service.method(INTERFACE_NAME, out_signature="i")
    def PositionGet(self):
        """
            Returns the playing position (will be [0, track_length] in
            milliseconds)
        """
        return int(player.PLAYER.get_position() / 1000000)

    def track_change_cb(self, type, object, data):
        """
            Callback will emit the dbus signal TrackChange with the current
            songs metadata
        """
        metadata = self.GetMetadata()
        self.TrackChange(metadata)

    def status_change_cb(self, type, object, data):
        """
            Callback will emit the dbus signal StatusChange with the current
            status
        """
        struct = self.GetStatus()
        self.StatusChange(struct)

    def caps_change_cb(self, type, object, data):
        """
            Callback will emit the dbus signal CapsChange with the current Caps
        """
        caps = self.GetCaps()
        self.CapsChange(caps)

    @dbus.service.signal(INTERFACE_NAME, signature="a{sv}")
    def TrackChange(self, metadata):
        """
            Signal is emitted when the "Media Player" plays another "Track".
            Argument of the signal is the metadata attached to the new "Track"
        """
        pass

    @dbus.service.signal(INTERFACE_NAME, signature="(iiii)")
    def StatusChange(self, struct):
        """
            Signal is emitted when the status of the "Media Player" change. The
            argument has the same meaning as the value returned by GetStatus.
        """
        pass

    @dbus.service.signal(INTERFACE_NAME)
    def CapsChange(self):
        """
            Signal is emitted when the "Media Player" changes capabilities, see
            GetCaps method.
        """
        pass

