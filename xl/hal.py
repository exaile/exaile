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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import logging, threading, time
import dbus

from xl import common, providers, event, devices, settings
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

class UDisks(providers.ProviderHandler):
    """
        Provides support for UDisks devices.

        If the D-Bus connection fails, this object will grow a "failed"
        attribute with True as the value. Plugins should check for this when
        registering if they want to provide HAL fallback. FIXME: There's a race
        condition here.
    """

    # States: start -> init -> addremove <-> listening -> end.
    # The addremove state acts as a lock against concurrent changes.

    def __init__(self, devicemanager):
        self._lock = lock = threading.Lock()
        self._state = 'init'
        logger.debug("UDisks: state = init")

        providers.ProviderHandler.__init__(self, 'udisks')
        self.devicemanager = devicemanager

        self.bus = self.obj = self.iface = None
        self.devices = {}
        self.providers = {}

    #~ @common.threaded
    def connect(self):
        assert self._state == 'init'
        logger.debug("Connecting to UDisks")
        try:
            self.bus = bus = dbus.SystemBus()
            self.obj = obj = bus.get_object('org.freedesktop.UDisks', '/org/freedesktop/UDisks')
            self.iface = iface = dbus.Interface(obj, 'org.freedesktop.UDisks')
            iface.connect_to_signal('DeviceAdded', self._udisks_device_added)
            iface.connect_to_signal('DeviceRemoved', self._udisks_device_removed)
            iface.connect_to_signal('DeviceChanged', self._udisks_device_added)
            logger.info("Connected to UDisks")
            event.log_event("hal_connected", self, None)
        except Exception:
            logger.warning("Failed to connect to UDisks, " \
                    "autodetection of devices will be disabled.")
            common.log_exception()
            self._state = 'listening'
            logger.debug("UDisks: state = listening")
            self.failed = True
            return
        self._state = 'addremove'
        logger.debug("UDisks: state = addremove")
        self._add_all()
        self._state = 'listening'
        logger.debug("UDisks: state = listening")

    def _add_all(self):
        assert self._state == 'addremove'
        for path in self.iface.EnumerateDevices():
            self._add_device(path)

    def _add_device(self, path=None, obj=None):
        """
            Call with either path or obj (obj gets priority). Not thread-safe.
        """
        assert self._state == 'addremove'
        if obj is None:
            obj = self.bus.get_object('org.freedesktop.UDisks', path)
        old, new = self._get_provider_for(obj)
        if new is not None:
            device = new.create_device(obj)
            if new is old and device is self.devices[path]:
                return # Exactly the same device
        if old is not None:
            self.devicemanager.remove_device(self.devices[path])
        if new is None:
            return
        try:
            device.autoconnect()
        except:
            logger.exception("Failed autoconnecting device " + str(device))
        else:
            self.devicemanager.add_device(device)
            self.providers[path] = new
            self.devices[path] = device

    def _get_provider_for(self, obj):
        """
            Return (old_provider, old_priority), (new_provider, new_priority).
            Not thread-safe.
        """
        assert self._state == 'addremove'
        highest_prio = -1
        highest = None
        old = self.providers.get(obj.object_path)
        for provider in self.get_providers():
            priority = provider.get_priority(obj)
            if priority is None: continue
            # Find highest priority, preferring old provider.
            if priority > highest_prio or \
                    (priority == highest_prio and provider is old):
                highest_prio = priority
                highest = provider
        return old, highest

    def _remove_device(self, path):
        assert self._state == 'addremove'
        try:
            self.devicemanager.remove_device(self.devices[path])
            del self.devices[path]
        except KeyError:
            logger.warning("UDisks: Can't remove device (not found): " + path)

    def _udisks_device_added(self, path):
        logger.debug("UDisks: Device added: " + str(path))
        if self._addremove():
            self._add_device(path)
            self._state = 'listening'
            logger.debug("UDisks: state = listening (_device_added)")

    def _udisks_device_removed(self, path):
        if self._addremove():
            try:
                self._remove_device(path)
                logger.debug("UDisks: Device removed: " + str(path))
            except KeyError: # Not ours
                pass
            self._state = 'listening'
            logger.debug("UDisks: state = listening")

    # FIXME: Handle provider add/remove (following code unused & untested).

    def on_provider_added(self, provider):
        if self._addremove():
            self._connect_all()
            self._state = 'listening'
            logger.debug("UDisks: state = listening")

    def on_provider_removed(self, provider):
        if self._addremove():
            for path, provider_ in self.providers.iteritems():
                if provider_ is provider:
                    self._remove_device(path)
            self._state = 'listening'
            logger.debug("UDisks: state = listening")

    def _addremove(self):
        """
            Helper to transition safely from listening to addremove state.

            Returns whether the transition happens.
        """
        i = 0
        while True:
            with self._lock:
                if self._state == 'listening':
                    self._state = 'addremove'
                    logger.debug("UDisks: state = addremove")
                    return True
            # If active state is init, we sleep and try again a few times.
            # TODO: Whose thread is this we are blocking?
            if i == 5:
                logger.error("UDisks: Failed to acquire lock. Ignoring device event.")
                return False
            i += 1
            time.sleep(1)

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

class UDisksProvider:
    VERY_LOW, LOW, NORMAL, HIGH, VERY_HIGH = range(0, 101, 25)
    def get_priority(self, obj):
        pass  # return: int [0..100] or None
    def get_device(self, obj):
        pass  # return: xl.devices.Device


# vim: et sts=4 sw=4
