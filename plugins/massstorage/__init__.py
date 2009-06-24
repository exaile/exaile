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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from xl import providers, collection, common
from xl.nls import gettext as _
from xl.hal import Handler
from xl.devices import Device
import dbus
import logging, os
logger = logging.getLogger(__name__)

PROVIDER = None


def enable(exaile):
    global PROVIDER
    PROVIDER = MassStorageHandler()
    providers.register("hal", PROVIDER)

def disable(exaile):
    global PROVIDER
    providers.unregister("hal", PROVIDER)
    PROVIDER = None

class MassStorageDevice(Device):
    def __init__(self, mountpoints, name=""):
        if len(mountpoints) == 0:
            raise ValueError, "Must specify at least one mount point"
        if not name:
            name = mountpoints[0].split(os.sep)[-1]
        Device.__init__(self, name)
        self.mountpoints = mountpoints

    def connect(self):
        self.mountpoints = [ x for x in self.mountpoints if os.path.exists(x) ]
        if self.mountpoints == []:
            raise IOError, "Mountpoint does not exist"
        for mountpoint in self.mountpoints:
            library = collection.Library(mountpoint)
            self.collection.add_library(library)
        self.connected = True # set this here so the UI can react 

    def disconnect(self):
        self.collection = collection.Collection(name=self.name)
        self.connected = False


class MassStorageHandler(Handler):
    name = "massstorage"
    def is_type(self, device, capabilities):
        if "portable_audio_player" in capabilities:
            if "storage" in device.GetProperty(
                    "portable_audio_player.access_method.protocols"):
                return True
        return False

    def get_udis(self, hal):
        udis = hal.hal.FindDeviceByCapability("portable_audio_player")
        ret = []
        for udi in udis:
            dev_obj = hal.bus.get_object("org.freedesktop.Hal", udi)
            device = dbus.Interface(dev_obj, "org.freedesktop.Hal.Device")
            if device.PropertyExists(
                    "portable_audio_player.access_method.protocols") and \
                    "storage" in device.GetProperty(
                    "portable_audio_player.access_method.protocols"):
                ret.append(udi)
        return ret

    def device_from_udi(self, hal, udi):
        mass_obj = hal.bus.get_object("org.freedesktop.Hal", udi)
        mass = dbus.Interface(mass_obj, "org.freedesktop.Hal.Device")
        if "storage" not in mass.GetProperty(
                "portable_audio_player.access_method.protocols"):
            return

        mountpoints = []
        udis = hal.hal.FindDeviceStringMatch("info.parent", udi)
        for u in udis:
            obj = hal.bus.get_object("org.freedesktop.Hal", u)
            dev = dbus.Interface(obj, "org.freedesktop.Hal.Device")
            if dev.GetProperty("volume.is_mounted") == True:
                mountpoints.append(str(dev.GetProperty("volume.mount_point")))

        if mountpoints == []:
            return

        name = mass.GetProperty("info.vendor") + " " + \
                mass.GetProperty("info.product")
        massdev = MassStorageDevice(mountpoints, name)

        return massdev


