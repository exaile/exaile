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
        self.exaile = exaile
        self.mpris_root = None
        self.mpris_tracklist = None
        self.mpris_player = None
        self.bus = None

    def release(self):
        for obj in (self.mpris_root, self.mpris_tracklist, self.mpris_player):
            if obj is not None:
                obj.remove_from_connection()
        self.mpris_root = None
        self.mpris_tracklist = None
        self.mpris_player = None
        if self.bus is not None:
            self.bus.get_bus().release_name(self.bus.get_name())

    def acquire(self):
        self._acquire_bus()
        self._add_interfaces()

    def _acquire_bus(self):
        if self.bus is not None:
            self.bus.get_bus().request_name(OBJECT_NAME)
        else:
            self.bus = dbus.service.BusName(OBJECT_NAME, bus=dbus.SessionBus())

    def _add_interfaces(self):
        self.mpris_root = mpris_root.ExaileMprisRoot(self.exaile, self.bus)
        self.mpris_tracklist = mpris_tracklist.ExaileMprisTrackList(
                                                        self.exaile, 
                                                        self.bus)
        self.mpris_player = mpris_player.ExaileMprisPlayer(
                                                        self.exaile,
                                                        self.bus)
