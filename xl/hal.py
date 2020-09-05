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
import threading
import time
import dbus

from xl import providers, event
from xl.main import common

logger = logging.getLogger(__name__)


class UDisksPropertyWrapper:
    """
    Wrapper around an org.freedesktop.DBus.Properties interface

    You shouldn't need to create this, use UDisksDBusWrapper.props
    """

    def __init__(self, obj, iface_type):
        self.obj = obj  # properties object
        self.iface_type = iface_type

    def __getattr__(self, name):
        return lambda *a, **k: self.obj.__getattr__(name)(
            *((self.iface_type,) + a), **k
        )

    # def connect_on_changed(self, fn):
    #    '''Connect to the PropertiesChanged signal'''
    #    return self.obj.connect_to_signal('PropertiesChanged', fn, self.iface_type)

    def __repr__(self):
        return '<UDisksPropertyWrapper: %s>' % self.iface_type


class UDisksDBusWrapper:
    """
    Simple wrapper to make life easier. Assume that we only are
    using this to get properties off the 'primary' interface.

    Assumes that you are only asking for properties on the interface
    associated with the object path.

    Example usage:

        obj = get_object_by_path('/org/freedesktop/UDisks2/drives/foo')
        print(obj.props.Get('Device'))

    You shouldn't need to create this, use get_object_py_path.
    """

    __slots__ = ['obj', 'iface_type', '_iface', '_props_iface', 'path']

    def __init__(self, bus, root, path, iface_type):
        self.obj = bus.get_object(root, path)
        self.iface_type = iface_type
        self._iface = None
        self._props_iface = None

    def __getattr__(self, member):
        return self.iface.__getattr__(member)

    def connect_to_signal(self, *a, **k):
        '''Connect to a signal on the object's primary interface type'''
        return self.iface.connect_to_signal(*a, **k)

    @property
    def iface(self):
        '''Returns a dbus.Interface for the object's primary interface type'''
        if self._iface is None:
            self._iface = dbus.Interface(self.obj, self.iface_type)
        return self._iface

    @property
    def object_path(self):
        return self.obj.object_path

    @property
    def props(self):
        '''Returns a dbus.Interface for org.freedesktop.DBus.Properties'''
        if self._props_iface is None:
            iface = dbus.Interface(self.obj, 'org.freedesktop.DBus.Properties')
            self._props_iface = UDisksPropertyWrapper(iface, self.iface_type)
        return self._props_iface

    def __repr__(self):
        return '<UDisksDBusWrapper: %s (%s)>' % (self.iface_type, self.path)


class UDisksBase(providers.ProviderHandler):
    """
    Provides support for UDisks (1 and 2) devices. To get properties
    of devices, the get_object_for_path function will return a convenient
    wrapper to use for accessing properties and such on it.

    Implements the udisks and udisks2 service for providers. Providers
    should override the UDisksProvider interface.

    Plugins should not try to connect to UDisks until exaile has finished
    loading.
    """

    # States: start -> init -> addremove <-> listening -> end.
    # The addremove state acts as a lock against concurrent changes.

    def __init__(self, devicemanager):
        self._lock = threading.Lock()
        self._state = 'init'

        providers.ProviderHandler.__init__(self, self.name)
        self.devicemanager = devicemanager

        self.bus = None
        self.devices = {}
        self.providers = {}

    def connect(self):
        assert self._state == 'init'
        logger.debug("Connecting to %s", self.name)
        try:
            self.obj = self._connect()
            logger.info("Connected to %s", self.name)
            event.log_event("hal_connected", self, None)
        except Exception:
            logger.info(
                "Failed to connect to %s, automatic detection of "
                "devices will be disabled.",
                self.name,
            )
            return False

        self._state = 'addremove'
        logger.debug("%s: state = addremove", self.name)
        self._add_all(self.obj)
        self._state = 'listening'
        logger.debug("%s: state = listening", self.name)
        return True

    #
    # Public API
    #

    def get_object_by_path(self, path):
        """
        Call this to retrieve a UDisksDBusWrapper object for the path
        of the object you want to retrieve.

        :param path: The udisks path of the object you want to retrieve

        :returns: UDisksDBusWrapper object
        :raises: KeyError if the object path/type is not supported
        """

        for p, iface_type in self.paths:
            if path.startswith(p):
                return UDisksDBusWrapper(self.bus, self.root, path, iface_type)

        raise KeyError("Unsupported path %s" % path)

    #
    # subclasses must implement these
    #

    def _connect(self):
        raise NotImplementedError()

    def _add_all(self, obj):
        raise NotImplementedError()

    #
    # Private API
    #

    def _add_device(self, path, obj=None):
        """
        Call with either path or obj (obj gets priority). Not thread-safe.
        """
        assert self._state == 'addremove'

        if obj is None:
            obj = self.get_object_by_path(path)

        # In the following code, `old` and `new` are providers, while
        # `self.devices[path]` and `device` are old/new devices. There are
        # several possible code paths that should be correctly handled:
        # - No old nor new provider for this path.
        # - Provider changes (nothing to something, something to nothing,
        #   something to something else); obviously device changes as well.
        # - Provider stays the same, but device changes (i.e. instant media-
        #   swapping; not sure it can happen).
        # - Provider and device stay the same.
        old, new = self._get_provider_for(obj)

        if new is None:
            if old is not None:
                self._remove_device(path)
            return

        device = new.get_device(obj, self)
        if new is old and device is self.devices[path]:
            return  # Exactly the same device

        if old is not None:
            self._remove_device(path)

        if new is None:
            return
        try:
            device.autoconnect()
        except Exception:
            logger.exception("%s: Failed autoconnecting device %s", self.name, device)
        else:
            self.devicemanager.add_device(device)
            self.providers[path] = new
            self.devices[path] = device

    def _on_change(self, path):

        assert self._state == 'addremove'

        obj = self.get_object_by_path(path)

        provider = self.providers.get(obj.object_path)
        if provider is None:
            self._add_device(path, obj)
        else:
            remove = provider.on_device_changed(obj, self, self.devices[path])
            if remove == 'remove':
                self._remove_device(path)

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
            priority = provider.get_priority(obj, self)
            if priority is None:
                continue
            # Find highest priority, preferring old provider.
            if priority > highest_prio or (
                priority == highest_prio and provider is old
            ):
                highest_prio = priority
                highest = provider
        return old, highest

    def _remove_device(self, path):
        assert self._state == 'addremove'

        self.devicemanager.remove_device(self.devices[path])
        del self.devices[path]
        del self.providers[path]

    def _udisks_device_added(self, *args):
        path = args[0]
        logger.debug("%s: Device added: %s", self.name, path)
        if self._addremove():
            try:
                self._add_device(path)
            finally:
                self._state = 'listening'
                logger.debug("%s: state = listening (_device_added)", self.name)

    def _udisks_device_changed(self, *args):
        path = args[0]
        logger.debug("%s: Device changed: %s", self.name, path)
        if self._addremove():
            try:
                self._on_change(path)
            finally:
                self._state = 'listening'
                logger.debug("%s: state = listening (_device_added)", self.name)

    def _udisks_device_removed(self, *args):
        path = args[0]
        if self._addremove():
            try:
                self._remove_device(path)
                logger.debug("%s: Device removed: %s", path, self.name)
            except KeyError:  # Not ours
                pass
            finally:
                self._state = 'listening'
                logger.debug("%s: state = listening (_device_removed)", self.name)

    def on_provider_added(self, provider):
        if self._addremove():
            try:
                self._add_all(self.obj)
            finally:
                self._state = 'listening'
                logger.debug("%s: state = listening (_provider_added)", self.name)

    def on_provider_removed(self, provider):
        if self._addremove():
            try:
                to_remove = []
                for path, provider_ in self.providers.items():
                    if provider_ is provider:
                        to_remove.append(path)

                for path in to_remove:
                    self._remove_device(path)
            finally:
                self._state = 'listening'
                logger.debug("%s: state = listening (_provider_removed)", self.name)

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
                    logger.debug("%s: state = addremove", self.name)
                    return True

            if i == 50:
                logger.error(
                    "%s: Failed to acquire lock. Ignoring device event.", self.name
                )
                return False
            i += 1
            time.sleep(0.1)


class UDisks2(UDisksBase):

    name = 'udisks2'
    root = 'org.freedesktop.UDisks2'
    paths = [
        ('/org/freedesktop/UDisks2/block_devices/', 'org.freedesktop.UDisks2.Block'),
        ('/org/freedesktop/UDisks2/drives/', 'org.freedesktop.UDisks2.Drive'),
        ('/org/freedesktop/UDisks2', 'org.freedesktop.DBus.ObjectManager'),
    ]

    def _connect(self):

        self.bus = dbus.SystemBus()
        obj = self.get_object_by_path('/org/freedesktop/UDisks2')

        obj.connect_to_signal('InterfacesAdded', self._udisks_device_added)
        obj.connect_to_signal('InterfacesRemoved', self._udisks_device_removed)

        # listen for PropertiesChanged events on any UDisks2 object
        self.bus.add_signal_receiver(
            self._udisks2_properties_changed,
            signal_name='PropertiesChanged',
            dbus_interface='org.freedesktop.DBus.Properties',
            bus_name='org.freedesktop.UDisks2',
            path_keyword='path',
        )

        return obj

    def _udisks2_properties_changed(self, *args, **kwargs):
        # TODO: this is inefficient, probably should just let the
        #       provider know what properties changed. would need
        #       to have the consumer let us know what to subscribe to
        self._udisks_device_changed(kwargs['path'])

    def _add_all(self, obj):
        assert self._state == 'addremove'
        for path in obj.GetManagedObjects():
            self._add_device(path)


class Handler:
    """
    The HAL provider interface
    """

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
    """
    The UDisksProvider interface. Works for UDisks 1 and 2, but you should
    implement separate providers for each, as the object types and
    properties are different.

    This API is subject to change.
    """

    VERY_LOW, LOW, NORMAL, HIGH, VERY_HIGH = range(0, 101, 25)

    def get_priority(self, obj, udisks):
        """
        Called on initial connect of a device. The provider should
        return a priority value indicating its interest in handling
        the device.

        :param obj: A UDisksPropertyWrapper object for the device path
        :param udisks: The UDisksBase object

        :returns: An integer [0..100] indicating priority, or None if it
                  cannot handle the device
        """

    def get_device(self, obj, udisks):
        """
        Called when the device is assigned to the provider (e.g., it
        indicated the highest priority).

        :param obj: A UDisksPropertyWrapper object for the device path
        :param udisks: The UDisksBase object

        :returns: xl.devices.Device derived object for the device
        """

    def on_device_changed(self, obj, udisks, device):
        """
        Called when UDisks indicates that a property of the device has
        changed. If useful, the provider should forward relevant change
        actions to its device object.

        :param obj: A UDisksPropertyWrapper object for the device path
        :param udisks: The UDisksBase object
        :param device: Object returned from get_device

        :returns: 'remove' to remove the device from the provider, other
                  values ignored.
        """


# vim: et sts=4 sw=4
