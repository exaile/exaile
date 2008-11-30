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

import dbus

from xl import common, providers

import logging
logger = logging.getLogger(__name__)


class HAL(providers.ProviderHandler):
    """
        HAL interface
    """
    def __init__(self, devicemanager):
        providers.ProviderHandler.__init__(self, "hal")
        self.devicemanager = devicemanager
        
        self.bus = None
        self.hal = None

        self.hal_devices = {}

    def connect(self):
        try:
            self.bus = dbus.SystemBus()
            hal_obj = self.bus.get_object('org.freedesktop.Hal', 
                '/org/freedesktop/Hal/Manager')
            self.hal = dbus.Interface(hal_obj, 'org.freedesktop.Hal.Manager')
            for p in self.get_providers():
                self.on_new_provider(p)
            self.setup_device_events()
            logger.debug(_("Connected to HAL"))
            return True
        except:
            logger.warning(_("Failed to connect to HAL, autodetection of devices will be disabled."))
            return False

    def on_new_provider(self, provider):
        for udi in provider.get_udis(self):
            self.add_device(udi)

    def on_del_provider(self, provider):
        pass #TODO: disconnect and remove all devices of this type

    def get_handler(self, udi):
        dev_obj = self.bus.get_object("org.freedesktop.Hal", udi)
        device = dbus.Interface(dev_obj, "org.freedesktop.Hal.Device")
        try:
            capabilities = device.GetProperty("info.capabilities")
        except dbus.exceptions.DBusException,e:
            if e.get_dbus_name() == "org.freedesktop.Hal.NoSuchProperty":
                return None
            else:
                common.log_exception(logger)
        for handler in self.get_providers():
            if handler.is_type(device, capabilities):
                return handler
        return None

    @common.threaded
    def add_device(self, device_udi):
        handler = self.get_handler(device_udi)
        if handler is None:
            logger.debug(_("Found no HAL device handler for %s")%device_udi)
            return
        logger.debug(_("Found new %s device at %s")%(handler.name, device_udi))

        dev = handler.device_from_udi(self, device_udi)
        if not dev: return
        dev.connect()

        self.devicemanager.add_device(dev)
        self.hal_devices[device_udi] = dev

    def remove_device(self, device_udi):
        try:
            self.devicemanager.remove_device(self.hal_devices[device_udi])
            del self.hal_devices[device_udi]
        except KeyError:
            pass

    def setup_device_events(self):
        self.bus.add_signal_receiver(self.add_device,
                "DeviceAdded")
        self.bus.add_signal_receiver(self.remove_device,
                "DeviceRemoved")


class Handler(object):
    name = 'base'
    def __init__(self):
        pass

    def is_type(self, device, capabilities):
        return False
    
    def get_udis(self, hal):
        return []

    def device_from_udi(self, hal, udi):
        pass


# vim: et sts=4 sw=4

