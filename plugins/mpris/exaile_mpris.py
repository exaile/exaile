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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
"""
An implementation of the MPRIS D-Bus protocol for use with Exaile
"""

import dbus
import dbus.service
import logging

import mpris_root
import mpris_tracklist
import mpris_player

LOG = logging.getLogger("exaile.plugins.mpris.exaile_mpris")

OBJECT_NAME = 'org.mpris.exaile'


class ExaileMpris(object):

    """
        Controller for various MPRIS objects.
    """

    def __init__(self, exaile=None):
        """
            Constructs an MPRIS controller. Note, you must call acquire()
        """
        self.exaile = exaile
        self.mpris_root = None
        self.mpris_tracklist = None
        self.mpris_player = None
        self.bus = None

    def release(self):
        """
            Releases all objects from D-Bus and unregisters the bus
        """
        for obj in (self.mpris_root, self.mpris_tracklist, self.mpris_player):
            if obj is not None:
                obj.remove_from_connection()
        self.mpris_root = None
        self.mpris_tracklist = None
        self.mpris_player = None
        if self.bus is not None:
            self.bus.get_bus().release_name(self.bus.get_name())

    def acquire(self):
        """
            Connects to D-Bus and registers all components
        """
        self._acquire_bus()
        self._add_interfaces()

    def _acquire_bus(self):
        """
            Connect to D-Bus and set self.bus to be a valid connection
        """
        if self.bus is not None:
            self.bus.get_bus().request_name(OBJECT_NAME)
        else:
            self.bus = dbus.service.BusName(OBJECT_NAME, bus=dbus.SessionBus())

    def _add_interfaces(self):
        """
            Connects all interfaces to D-Bus
        """
        self.mpris_root = mpris_root.ExaileMprisRoot(self.exaile, self.bus)
        self.mpris_tracklist = mpris_tracklist.ExaileMprisTrackList(
            self.exaile,
            self.bus)
        self.mpris_player = mpris_player.ExaileMprisPlayer(
            self.exaile,
            self.bus)
