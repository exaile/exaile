# Copyright (C) 2009-2010 Aren Olson
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

from xl import providers, collection
from xl.hal import Handler
from xl.devices import Device
import dbus
import logging
import os

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
            raise ValueError("Must specify at least one mount point")
        if not name:
            name = mountpoints[0].split(os.sep)[-1]
        Device.__init__(self, name)
        self._mountpoints = mountpoints
        self.mountpoints = []

    def connect(self):
        self.mountpoints = [
            str(x) for x in self._mountpoints if str(x) != "" and os.path.exists(str(x))
        ]
        if self.mountpoints == []:
            raise IOError("Device is not mounted.")
        for mountpoint in self.mountpoints:
            library = self.library_class(mountpoint)
            self.collection.add_library(library)
        self.transfer = collection.TransferQueue(self.collection.get_libraries()[0])
        self.connected = True  # set this here so the UI can react

    def disconnect(self):
        self.collection = collection.Collection(name=self.name)
        self.mountpoints = []
        self.transfer = None
        self.connected = False


class HalMountpoint:
    """
    Class to represent a mountpoint so we can delay HAL
    mountpoint resolution.
    """

    def __init__(self, hal, udi):
        self.hal = hal
        self.udi = udi

    def __str__(self):
        udis = self.hal.hal.FindDeviceStringMatch("info.parent", self.udi)
        for u in udis:
            obj = self.hal.bus.get_object("org.freedesktop.Hal", u)
            dev = dbus.Interface(obj, "org.freedesktop.Hal.Device")
            if dev.GetProperty("volume.is_mounted") is True:
                return str(dev.GetProperty("volume.mount_point"))
        return ""


class MassStorageHandler(Handler):
    name = "massstorage"

    def is_type(self, device, capabilities):
        if "portable_audio_player" in capabilities:
            try:
                if "storage" in device.GetProperty(
                    "portable_audio_player.access_method.protocols"
                ):
                    return 10
            except dbus.exceptions.DBusException as e:
                if not e.get_dbus_name() == "org.freedesktop.Hal.NoSuchProperty":
                    logger.exception("Portable audio player without storage property")
        return 0

    def get_udis(self, hal):
        udis = hal.hal.FindDeviceByCapability("portable_audio_player")
        ret = []
        for udi in udis:
            dev_obj = hal.bus.get_object("org.freedesktop.Hal", udi)
            device = dbus.Interface(dev_obj, "org.freedesktop.Hal.Device")
            if device.PropertyExists(
                "portable_audio_player.access_method.protocols"
            ) and "storage" in device.GetProperty(
                "portable_audio_player.access_method.protocols"
            ):
                ret.append(udi)
        return ret

    def device_from_udi(self, hal, udi):
        mass_obj = hal.bus.get_object("org.freedesktop.Hal", udi)
        mass = dbus.Interface(mass_obj, "org.freedesktop.Hal.Device")
        if "storage" not in mass.GetProperty(
            "portable_audio_player.access_method.protocols"
        ):
            return

        u = mass.GetProperty("portable_audio_player.storage_device")
        mountpoints = [HalMountpoint(hal, u)]

        name = mass.GetProperty("info.vendor") + " " + mass.GetProperty("info.product")
        massdev = MassStorageDevice(mountpoints, name)

        return massdev
