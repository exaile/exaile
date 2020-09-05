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
Devices

contains the DeviceManager and some generic Device classes
"""

from typing import Iterable
from xl import event, collection


class TransferNotSupportedError(Exception):
    pass


class Device:
    """
    a device

    must be subclassed for use
    """

    class_autoconnect = False
    library_class = collection.Library

    def __init__(self, name):
        self.name = name
        self.collection = collection.Collection(name=self.name)
        self.playlists = []
        self._connected = False
        self.transfer = None  # subclasses need to override this
        # if they want transferring

    def __get_connected(self):
        return self._connected

    def __set_connected(self, val):
        prior = self._connected
        self._connected = val
        if prior != val:
            if val:
                event.log_event("device_connected", self, self)
            else:
                event.log_event("device_disconnected", self, self)

    connected = property(__get_connected, __set_connected)

    def get_name(self):
        return self.name

    def autoconnect(self):
        if self.class_autoconnect:
            self.connect()

    def is_connected(self):
        return self.connected

    def connect(self):
        """
        connects to the device, creating Collections and Playlists
        as appropriate
        """
        raise NotImplementedError

    def disconnect(self):
        """
        disconnect from the device. should clear all stored metadata
        """
        raise NotImplementedError

    def get_collection(self):
        """
        returns the device's collection, if applicable
        """
        return self.collection

    def get_playlists(self):
        """
        returns a list of all playlists on the device, if any
        """
        return self.playlists

    def add_tracks(self, tracks):
        """
        Send tracks to the device
        """
        if not self.transfer:
            raise TransferNotSupportedError(
                "Device class does not " "support transfer."
            )
        self.transfer.enqueue(tracks)

    def start_transfer(self):
        if not self.transfer:
            raise TransferNotSupportedError(
                "Device class does not " "support transfer."
            )
        self.transfer.transfer()


class KeyedDevice(Device):
    """
    A utility class to inherit from that will return cached instances
    of your device if the device object is created with the same key.

    A device that inherits from this MUST have the key as the first
    argument to the __init__ function.

    @warning The __init__ function will be called again for devices
    that are created multiple times.
    """

    @staticmethod
    def __new__(cls, key):

        devices = getattr(cls, '__devices', {})

        device = devices.get(key, None)
        if device is None:
            device = Device.__new__(cls)
            device.__initialized = False
            device.__key = key
            devices[key] = device

        setattr(cls, '__devices', devices)
        return device

    def __init__(self, name):
        if self.__initialized:
            return

        # don't call this twice..
        Device.__init__(self, name)
        self.__initialized = True

    @classmethod
    def destroy(cls, device):
        """
        Call this to remove the device from the internal list
        """
        del getattr(cls, '__devices')[device.__key]


class DeviceManager:
    """
    manages devices
    """

    def __init__(self):
        self.devices = {}

    def add_device(self, device: Device):
        # make sure we don't overwrite existing devices
        count = 3
        if device.get_name() in self.devices:
            device.name += " (2)"
        while device.get_name() in self.devices:
            device.name = device.name[:-4] + " (%s)" % count
            count += 1

        self.devices[device.get_name()] = device
        event.log_event("device_added", self, device)

    def remove_device(self, device: Device):
        try:
            if device.connected:
                device.disconnect()
            del self.devices[device.get_name()]
        except KeyError:
            pass
        event.log_event("device_removed", self, device)

    def get_devices(self) -> Iterable[Device]:
        return self.devices.values()


# vim: et sts=4 sw=4
