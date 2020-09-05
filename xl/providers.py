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
    A generic framework for service providers, recommended to be used
    whenever there are multiple ways of accomplishing a task or multiple
    sources can offer the required data.
"""

from xl import event
import logging

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    The overall manager for services and providers for them
    """

    def __init__(self):
        self.services = {}

    def register_provider(self, servicename, provider, target=None):
        """
        Registers a provider for a service. The provider object is used
        by consumers of the service.

        Services can be targeted for a specific use. For example, if you
        have a widget that uses a service 'foo', if your object can perform
        a service only for a specific type of widget, then target would be
        set to the widget type.

        If you had a service that could perform 'foo' for all widgets, then
        target would be set to None, and all widgets could use your service.

        It is intended that most services should set target to None, with
        some narrow exceptions.

        :param servicename: the name of the service [string]
        :type servicename: string
        :param provider: the object that is the provider [object]
        :type provider: object
        :param target: a specific target for the service [object]
        :type target: object
        """
        service = self.services.setdefault(servicename, {})
        providers = service.setdefault(target, [])
        if provider not in providers:
            providers.append(provider)
            logger.debug(
                "Provider %(provider)s registered for service %(service)s "
                "with target %(target)s"
                % {'provider': provider.name, 'service': servicename, 'target': target}
            )
            event.log_event("%s_provider_added" % servicename, self, (provider, target))

    def unregister_provider(self, servicename, provider, target=None):
        """
        Unregisters a provider.

        :param servicename: the name of the service
        :type servicename: string
        :param provider: the provider to be removed
        :type provider: object
        :param target: a specific target for the service [object]
        :type target: object
        """
        if servicename not in self.services:
            return
        try:
            service = self.services[servicename]
            if provider in service[target]:
                service[target].remove(provider)
                logger.debug(
                    "Provider %(provider)s unregistered from "
                    "service %(service)s with target %(target)s"
                    % {
                        'provider': provider.name,
                        'service': servicename,
                        'target': target,
                    }
                )
                event.log_event(
                    "%s_provider_removed" % servicename, self, (provider, target)
                )
                if not service[target]:  # no values for target key then del it
                    del service[target]
        except KeyError:
            return

    def get_providers(self, servicename, target=None):
        """
        Returns a list of providers for the specified servicename.

        This will return providers targeted for a specific target AND
        providers not targeted towards any particular target.

        :param servicename: the service name to get providers for
        :type servicename: string
        :param target: the target of the service
        :type target: object
        :returns: list of providers
        :rtype: list of objects
        """
        try:
            service = self.services[servicename]
        except KeyError:
            return []

        try:
            generic = service[None]
        except KeyError:
            generic = []

        if target is None:
            return generic[:]

        try:
            specific = service[target]
        except KeyError:
            specific = []

        return specific + generic

    def get_provider(self, servicename, providername, target=None):
        """
        Returns a single identified provider

        This will return a provider either targeted for the specific
        target or a provider not targeted towards any particular target.

        :param servicename: The service name to get the provider for
        :type servicename: string
        :param providername: The provider name to identify the provider
        :type providername: string
        :param target: the target of the service
        :type target: object
        :returns: a provider or None
        :rtype: object
        """
        for provider in self.get_providers(servicename, target):
            if provider.name == providername:
                return provider

        return None


MANAGER = ProviderManager()
register = MANAGER.register_provider
unregister = MANAGER.unregister_provider
get = MANAGER.get_providers
get_provider = MANAGER.get_provider


class ProviderHandler:
    """
    Base class to handle providers
    for one specific service including
    notification about (un)registration
    """

    def __init__(self, servicename, target=None, simple_init=False):
        """
        Target is the object that the service is being performed for.
        Often, if the service is truly global and it doesn't make sense
        to target a service at a particular consumer, it can be None.

        :param servicename: the name of the service to handle
        :type servicename: string
        :param target: the target for a provided service. Generally,
                       this will be the object that uses the service
        :type target: string
        :param simple_init: call on_provider_added for every element
                            already registered on instantiation.
        """
        self.servicename = servicename
        self.target = target
        if simple_init:
            for provider in MANAGER.get_providers(servicename, target):
                self.on_provider_added(provider)
        event.add_ui_callback(self._add_callback, "%s_provider_added" % servicename)
        event.add_ui_callback(
            self._remove_callback, "%s_provider_removed" % servicename
        )

    def _add_callback(self, name, obj, ptuple):
        """
        Mediator to call actual callback
        for added providers
        """
        provider, target = ptuple
        if target is None or target is self.target:
            self.on_provider_added(provider)

    def on_provider_added(self, provider):
        """
        Called when a new provider is added

        :param provider: the new provider
        :type provider: object
        """
        pass  # for overriding

    def _remove_callback(self, name, obj, ptuple):
        """
        Mediator to call actual callback
        for removed providers
        """
        provider, target = ptuple
        if target is None or target is self.target:
            self.on_provider_removed(provider)

    def on_provider_removed(self, provider):
        """
        Called when a provider is removed

        :param provider: the removed provider
        :type provider: object
        """
        pass  # for overriding

    def get_providers(self):
        """
        Returns a list of providers for this service

        :returns: list of providers
        :rtype: list of objects
        """
        return MANAGER.get_providers(self.servicename, self.target)

    def get_provider(self, providername):
        """
        Returns a provider for this service.

        :param providername: The provider name to
            identify the provider
        :type providername: string
        :returns: A provider or None
        :rtype: object
        """
        return MANAGER.get_provider(self.servicename, providername, self.target)


class MultiProviderHandler:
    """
    This is useful for listening to multiple provider types

    TODO: optimize implementation, could be better
    """

    class _ProxyProvider(ProviderHandler):
        def __init__(self, servicename, target, simple_init, parent):
            self.parent = parent
            ProviderHandler.__init__(self, servicename, target, simple_init)

        def on_provider_added(self, provider):
            self.parent.on_provider_added(provider)

        def on_provider_removed(self, provider):
            self.parent.on_provider_removed(provider)

    def __init__(self, servicenames, target=None, simple_init=False):
        self.providers = []
        for servicename in servicenames:
            self.providers.append(
                MultiProviderHandler._ProxyProvider(
                    servicename, target, simple_init, self
                )
            )

    def on_provider_added(self, provider):
        """
        Called when a new provider is added

        :param provider: the new provider
        :type provider: object
        """

    def on_provider_removed(self, provider):
        """
        Called when a provider is removed

        :param provider: the removed provider
        :type provider: object
        """

    def get_providers(self):
        """
        Returns a list of providers for this service

        :returns: list of providers
        :rtype: list of objects
        """

        providers = []
        for provider in self.providers:
            providers.extend(provider.get_providers())
        return providers


# vim: et sts=4 sw=4
