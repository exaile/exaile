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

# Exaile plugin for iPod support, with autodetection

import sys, time
from xl import common
from xl.devices import Device
from xl.collection import Collection
from xl.trax import Track, is_valid_track
from xl import event, providers
from xl.hal import Handler
import gpod, gobject
import dbus

import logging
logger = logging.getLogger(__name__)

_MOUNT_TRIES = 5

# iPod device class
class iPod(Device):
    class_autoconnect = True
    def __init__(self, volume):
        self.volume = volume
        self.name = self.volume.GetProperty("volume.label")
        if not self.name: # This ipod has not yet been given a name
            self.name = "Apple iPod Music Player"
        Device.__init__(self, self.name)
        self.db = None
        self._is_mounted = volume.GetProperty("volume.is_mounted")
        self.mountpoint = None
        self.collection = Collection("Master")
        if self._is_mounted:
            self.mountpoint = str(volume.GetProperty("volume.mount_point"))
            self.open_db()
            self.populate_collection()

    def open_db(self):
        if self.db:
            return
        else:
            self.db = gpod.Database(mountpoint=self.mountpoint)

    def populate_collection(self):
        for track in self.db.get_master():
           track_path = self.mountpoint + track["ipod_path"].replace(":", "/")
           if is_valid_track(track_path):
               track_object = Track(track_path)
               if track_object:
                   self.collection.add(track_object)

    def disconnect(self):
        """
        Disconnect (or in this case 'unmount' the ipod)
        """
        self.connected = False
        self.db = None

    @common.threaded
    def connect(self):
        """
        Connect (or in this case 'mount' the ipod)
        """
        count = 0
        while count < _MOUNT_TRIES:
            is_mounted = self.volume.GetProperty("volume.is_mounted")
            if is_mounted: break
            logger.info("iPod not mounted yet, waiting 1 second...")
            time.sleep(1)
            count += 1

        if not is_mounted:
            logger.info("Waited %d seconds for a valid mount and could not "
                "find one.  Not autoconnecting iPod plugin." % _MOUNT_TRIES)
            return

        self.mountpoint = str(self.volume.GetProperty("volume.mount_point"))
        self.open_db()
        self.populate_collection()
        self.connected = True

# iPod provider handled
class iPodHandler(Handler):
    name="ipod"
    def __init__(self):
        Handler.__init__(self)
        self.bus = None

    def get_udis(self, hal):
        ret = []
        # Based on the code from: https://bugs.launchpad.net/exaile/+bug/135915
        self.bus = hal.bus # BAD
        dev_udi_list = hal.hal.FindDeviceStringMatch('info.category',
            'portable_audio_player')
        for udi in dev_udi_list:
            udiObj = hal.bus.get_object('org.freedesktop.Hal', udi)
            udiInt = dbus.Interface(udiObj, 'org.freedesktop.Hal.Device')
            if udiInt.PropertyExists('info.product') and \
                udiInt.GetProperty('info.product').lower() == 'ipod':
                volList = hal.hal.FindDeviceStringMatch('info.parent', udi)
                for volUdi in volList:
                    volObj = hal.bus.get_object('org.freedesktop.Hal', volUdi)
                    volInt = dbus.Interface(volObj,
                        'org.freedesktop.Hal.Device')
                    # The first partition contains ipod firmware,  which cannot
                    # be mounted (unless there's only one partition, as
                    # on this ipod nano)
                    if len(volList) == 1 or \
                        (volInt.PropertyExists('volume.partition.number') and \
                        int(volInt.GetProperty('volume.partition.number')) != 1):
                        ret.append(volUdi)
        return ret

    def is_type(self, device, capabilities):
        result = 0
        parent_udi = device.GetProperty("info.parent")
        parent_proxy = self.bus.get_object("org.freedesktop.Hal", parent_udi)
        parent_iface = dbus.Interface(parent_proxy, 'org.freedesktop.Hal.Device')
        try:
            parent_protocols = parent_iface.GetProperty(
                "portable_audio_player.access_method.protocols")
            if "ipod" in parent_protocols:
                result = 10
        except dbus.DBusException:
            result = 0

        return result

    def device_from_udi(self, hal, udi):
        device_proxy = hal.bus.get_object("org.freedesktop.Hal", udi)
        device_iface = dbus.Interface(device_proxy, 'org.freedesktop.Hal.Device')

        return iPod(device_iface)

ipod_provider = None

def enable(exaile):
    global ipod_provider
    ipod_provider = iPodHandler()
    providers.register("hal", ipod_provider)

def disable(exaile):
    global ipod_provider
    providers.unregister("hal", ipod_provider)
    ipod_provider = None
