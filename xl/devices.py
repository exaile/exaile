# Devices
#
# contains the DeviceManager and some generic Device classes
#

from xl import common, cd, event


class DeviceManager:
    """
        manages devices
    """
    def __init__(self):
        self.devices = {}

    def add_device(self, device):
        self.devices[device.get_name()] = device

    def remove_device(self, device):
        try:
            del self.devices[device.get_name()]
        except KeyError:
            pass

    def list_devices(self):
        return self.devices.values()

class Device:
    """
        a device

        must be subclassed for use
    """
    def __init__(self, name):
        self.name = name
        self.collection = None
        self.playlists = []

    def get_name(self):
        return self.name

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


class CDDevice(Device):
    """
        represents a CD
    """
    def __init__(self, dev="/dev/cdrom"):
        Device.__init__(self, dev)
        self.dev = dev

    def connect(self):
        cdpl = cd.CDPlaylist(device=self.dev)
        self.playlists.append(cdpl)

    def disconnect(self):
        self.playlists = []

