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

# Devices
#
# contains the DeviceManager and some generic Device classes
#

from xl import common, event


class DeviceManager(object):
    """
        manages devices
    """
    def __init__(self):
        self.devices = {}

    def add_device(self, device):
        # make sure we don't overwrite existing devices
        count = 3
        if device.get_name() in self.devices:
            device.name += " (2)"
        while device.get_name() in self.devices:
            device.name = device.name[:-4] + " (%s)"%count
            count += 1

        self.devices[device.get_name()] = device
        event.log_event("device_added", self, device)

    def remove_device(self, device):
        try:
            del self.devices[device.get_name()]
        except KeyError:
            pass
        event.log_event("device_removed", self, device)

    def list_devices(self):
        return self.devices.values()

class Device(object):
    """
        a device

        must be subclassed for use
    """
    class_autoconnect = True # BAD

    def __init__(self, name):
        self.name = name
        self.collection = None
        self.playlists = []
        self.connected = False

    def get_name(self):
        return self.name

    # will need revisiting when we get a UI device manager
    def autoconnect(self):
        if self.class_autoconnect == True:
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


# vim: et sts=4 sw=4

