# Copyright (C) 2009-2010 Abhisehk Mukherjee
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
"""MPRIS Specification implementation plugin for Exaile"""

__all__ = ["exaile_mpris",
        "mpris_player",
        "mpris_root",
        "mpris_tracklist",
        "mpris_tag_converter"]

import exaile_mpris
import logging

LOG = logging.getLogger("exaile.plugins.mpris")

_MPRIS = None

def enable(exaile):
    """Opens an object reference for D-BUS"""
    global _MPRIS
    LOG.debug("Enabling MPRIS")
    if _MPRIS is None:
        _MPRIS = exaile_mpris.ExaileMpris(exaile)
    _MPRIS.exaile = exaile
    _MPRIS.acquire()

def disable(exaile):
    """Closes the current connection to D-Bus"""
    LOG.debug("Disabling MPRIS")
    _MPRIS.release()
