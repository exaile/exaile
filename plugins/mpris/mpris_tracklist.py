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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""/TrackList object for MPRIS specification interface to Exaile

http://wiki.xmms2.xmms.se/wiki/MPRIS#.2FTrackList_object_methods
"""
import dbus
import dbus.service

import xl.trax
import xl.event
from xl import player
from xl.common import to_unicode

import mpris_tag_converter

INTERFACE_NAME = 'org.freedesktop.MediaPlayer'

class ExaileMprisTrackList(dbus.service.Object):

    """
        /TrackList object methods
    """

    def __init__(self, exaile, bus):
        dbus.service.Object.__init__(self, bus, '/TrackList')
        self.exaile = exaile
        self.tag_converter = mpris_tag_converter.ExaileTagConverter(exaile)
        for event in ('tracks_removed', 'tracks_added'):
            xl.event.add_callback(self.tracklist_change_cb, event)

    def __get_playlist(self):
        """
            Returns the list of tracks in the current playlist
        """
        return player.QUEUE.current_playlist.get_ordered_tracks()

    @dbus.service.method(INTERFACE_NAME,
            in_signature="i", out_signature="a{sv}")
    def GetMetadata(self, pos):
        """
            Gives all meta data available for element at given position in the
            TrackList, counting from 0

            Each dict entry is organized as follows
              * string: Metadata item name
              * variant: Metadata value
        """
        track = self.__get_playlist()[pos]
        return self.tag_converter.get_metadata(track)

    @dbus.service.method(INTERFACE_NAME, out_signature="i")
    def GetCurrentTrack(self):
        """
            Return the position of current URI in the TrackList The return
            value is zero-based, so the position of the first URI in the
            TrackList is 0. The behavior of this method is unspecified if
            there are zero elements in the TrackList.
        """
        try:
            return player.QUEUE.current_playlist.index(
                    player.PLAYER.current)
        except ValueError:
            return -1

    @dbus.service.method(INTERFACE_NAME, out_signature="i")
    def GetLength(self):
        """
            Number of elements in the TrackList
        """
        return len(player.QUEUE.current_playlist)

    @dbus.service.method(INTERFACE_NAME,
            in_signature="sb", out_signature="i")
    def AddTrack(self, uri, play_immediately):
        """
            Appends an URI in the TrackList.
        """
        uri = uri[7:]
        track = self.exaile.collection.get_track_by_loc(to_unicode(uri))
        if track is None:
            track = xl.trax.Track(uri)
        player.QUEUE.current_playlist.add(track)
        if play_immediately:
            player.QUEUE.play(track)
        return 0

    @dbus.service.method(INTERFACE_NAME, in_signature="i")
    def DelTrack(self, pos):
        """
            Appends an URI in the TrackList.
        """
        player.QUEUE.current_playlist.remove(pos)

    @dbus.service.method(INTERFACE_NAME, in_signature="b")
    def SetLoop(self, loop):
        """
            Sets the player's "repeat" or "loop" setting
        """
        player.QUEUE.current_playlist.set_repeat(loop)

    @dbus.service.method(INTERFACE_NAME, in_signature="b")
    def SetRandom(self, random):
        """
            Sets the player's "random" setting
        """
        player.QUEUE.current_playlist.set_random(random)

    def tracklist_change_cb(self, type, object, data):
        """
            Callback for a track list change
        """
        len = self.GetLength()
        self.TrackListChange(len)

    @dbus.service.signal(INTERFACE_NAME, signature="i")
    def TrackListChange(self, num_of_elements):
        """
            Signal is emitted when the "TrackList" content has changed:
              * When one or more elements have been added
              * When one or more elements have been removed
              * When the ordering of elements has changed

            The argument is the number of elements in the TrackList after the
            change happened.
        """
        pass

