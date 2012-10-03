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
"""/ Object for MPRIS specification interface to Exaile

http://wiki.xmms2.xmms.se/wiki/MPRIS#.2F_.28Root.29_object_methods
"""
import dbus
import dbus.service

from xl.nls import gettext as _

INTERFACE_NAME = 'org.freedesktop.MediaPlayer'

class ExaileMprisRoot(dbus.service.Object):

    """
        / (Root) object methods
    """

    def __init__(self, exaile, bus):
        dbus.service.Object.__init__(self, bus, '/')
        self.exaile = exaile

    @dbus.service.method(INTERFACE_NAME, out_signature="s")
    def Identity(self):
        """
            Identify the "media player"
        """
        return "Exaile %s" % self.exaile.get_version()

    @dbus.service.method(INTERFACE_NAME)
    def Quit(self):
        """
            Makes the "Media Player" exit.
        """
        self.exaile.quit()

    @dbus.service.method(INTERFACE_NAME, out_signature="(qq)")
    def MprisVersion(self):
        """
            Makes the "Media Player" exit.
        """
        return (1, 0)

