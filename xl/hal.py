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

import logging
import dbus

from xl import common, providers, event, devices, settings
from xl.nls import gettext as _

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

    @common.threaded
    def connect(self):
        try:
            self.bus = dbus.SystemBus()
            hal_obj = self.bus.get_object('org.freedesktop.Hal',
                '/org/freedesktop/Hal/Manager')
            self.hal = dbus.Interface(hal_obj, 'org.freedesktop.Hal.Manager')
            logger.debug("HAL Providers: %s" % repr(self.get_providers()))
            for p in self.get_providers():
                try:
                    self.on_provider_added(p)
                except:
                    logger.warning("Failed to load HAL devices for %s" % p.name)
                    common.log_exception(logger)
            self.setup_device_events()
            logger.debug("Connected to HAL")
            event.log_event("hal_connected", self, None)
        except:
            logger.warning("Failed to connect to HAL, " \
                    "autodetection of devices will be disabled.")

    def on_provider_added(self, provider):
        for udi in provider.get_udis(self):
            self.add_device(udi)

    def on_provider_removed(self, provider):
        pass #TODO: disconnect and remove all devices of this type

    def get_handler(self, udi):
        dev_obj = self.bus.get_object("org.freedesktop.Hal", udi)
        device = dbus.Interface(dev_obj, "org.freedesktop.Hal.Device")
        try:
            capabilities = device.GetProperty("info.capabilities")
        except dbus.exceptions.DBusException,e:
            if not e.get_dbus_name() == "org.freedesktop.Hal.NoSuchProperty":
                common.log_exception(logger)
            return None
        handlers = []
        for handler in self.get_providers():
            rank = handler.is_type(device, capabilities)
            if rank == 0:
                continue
            handlers.append((rank, handler))
        if handlers != []:
            return max(handlers)[1]
        return None

    def add_device(self, device_udi):
        if device_udi in self.hal_devices:
            logger.warning(
                    "Device %s already in hal list, skipping." % device_udi)
            return

        handler = self.get_handler(device_udi)
        if handler is None:
            logger.debug("Found no HAL device handler for %s" % device_udi)
            return

        dev = handler.device_from_udi(self, device_udi)
        if not dev:
            logger.debug("Failed to create device for %s" % device_udi)
            return

        logger.debug("Found new %(handler)s device at %(device_udi)s" %
                {'handler' : handler.name, 'device_udi' : device_udi})
        dev.autoconnect()

        self.devicemanager.add_device(dev)
        self.hal_devices[device_udi] = dev

    def remove_device(self, device_udi):
        logger.debug("Got request to remove %s" % device_udi)
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

