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

    def __init__(self, exaile):
        bus_name = dbus.service.BusName(OBJECT_NAME, bus=dbus.SessionBus())
        self.mpris_root = mpris_root.ExaileMprisRoot(exaile, bus_name)
        self.mpris_tracklist = mpris_tracklist.ExaileMprisTrackList(
                                                        exaile, bus_name)
        self.mpris_player = mpris_player.ExaileMprisPlayer(exaile, bus_name)

