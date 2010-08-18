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

"""
    A generic framework for service providers, recommended to be used
    whenever there are multiple ways of accomplishing a task or multiple
    sources can offer the required data.
"""

from xl import event
import logging
logger = logging.getLogger(__name__)

class ProviderManager(object):
    """
        The overall manager for services
        and providers for them
    """
    def __init__(self):
        self.services = {}

    def register_provider(self, servicename, provider):
        """
            Registers a provider.

            :param servicename: the name of the service [string]
            :type servicename: string
            :param provider: the object that is the provider [object]
            :type provider: object
        """
        if servicename not in self.services:
            self.services[servicename] = []
        self.services[servicename].append(provider)
        logger.debug(
            "Provider %(provider)s registered for service %(service)s" % {
                'provider' : provider.name,
                'service' : servicename
            }
        )
        event.log_event("%s_provider_added" % servicename, self, provider)

    def unregister_provider(self, servicename, provider):
        """
            Unregisters a provider.

            :param servicename: the name of the service
            :type servicename: string
            :param provider: the provider to be removed
            :type provider: object
        """
        if servicename not in self.services:
            return
        try:
            if provider in self.services[servicename]:
                self.services[servicename].remove(provider)
            logger.debug(
                "Provider %(provider)s unregistered from "
                "service %(service)s" % {
                    'provider' : provider.name,
                    'service' : servicename
                }
            )
            event.log_event("%s_provider_removed" % servicename, self, provider)
        except KeyError:
            return

    def get_providers(self, servicename):
        """
            Returns a list of providers for the specified servicename.

            :param servicename: the service name to get providers for
            :type servicename: string
            :returns: list of providers
            :rtype: list of objects
        """
        try:
            return self.services[servicename][:]
        except KeyError:
            return []

    def get_provider(self, servicename, providername):
        """
            Returns a single identified provider

            :param servicename: The service name to get the provider for
            :type servicename: string
            :param providername: The provider name to identify the provider
            :type providername: string
            :returns: a provider or None
            :rtype: object
        """
        try:
            providers = self.services[servicename]
        except KeyError:
            return None
        else:
            for provider in providers:
                if provider.name == providername:
                    return provider

        return None

MANAGER = ProviderManager()
register = MANAGER.register_provider
unregister = MANAGER.unregister_provider
get = MANAGER.get_providers
get_provider = MANAGER.get_provider

class ProviderHandler(object):
    """
        Base class to handle providers
        for one specific service including
        notification about (un)registration
    """
    def __init__(self, servicename):
        """
            :param servicename: the name of the service to handle
            :type servicename: string
        """
        self.servicename = servicename
        event.add_callback(self._add_callback,
            "%s_provider_added" % servicename)
        event.add_callback(self._remove_callback,
            "%s_provider_removed" % servicename)

    def _add_callback(self, name, obj, provider):
        """
            Mediator to call actual callback
            for added providers
        """
        self.on_provider_added(provider)

    def on_provider_added(self, provider):
        """
            Called when a new provider is added

            :param provider: the new provider
            :type provider: object
        """
        pass # for overriding

    def _remove_callback(self, name, obj, provider):
        """
            Mediator to call actual callback
            for removed providers
        """
        self.on_provider_removed(provider)

    def on_provider_removed(self, provider):
        """
            Called when a provider is removed

            :param provider: the removed provider
            :type provider: object
        """
        pass # for overriding

    def get_providers(self):
        """
            Returns a list of providers for this service

            :returns: list of providers
            :rtype: list of objects
        """
        return MANAGER.get_providers(self.servicename)

    def get_provider(self, providername):
        """
            Returns a provider for this service.

            :param providername: The provider name to
                identify the provider
            :type providername: string
            :returns: A provider or None
            :rtype: object
        """
        return MANAGER.get_provider(self.servicename, providername)

# vim: et sts=4 sw=4

