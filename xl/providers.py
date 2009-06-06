# Copyright (C) 2008-2009 Adam Olsen 
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

from xl.nls import gettext as _
from xl import event
import logging
logger = logging.getLogger(__name__)

class ProviderManager(object):
    def __init__(self):
        self.services = {}

    def register_provider(self, servicename, provider):
        if servicename not in self.services:
            self.services[servicename] = []
        self.services[servicename].append(provider)
        logger.debug(_("Provider %s registered for service %s") % \
                (provider.name, servicename))
        event.log_event("%s_provider_added"%servicename, self, provider)

    def unregister_provider(self, servicename, provider):
        if servicename not in self.services:
            return
        try:
            if provider in self.services[servicename]:
                self.services[servicename].remove(provider)
            logger.debug(_("Provider %s unregistered from service %s") % \
                    (provider.name, servicename))
            event.log_event("%s_provider_removed"%servicename, self, provider)
        except KeyError:
            return

    def get_providers(self, servicename):
        try:
            return self.services[servicename][:]
        except KeyError:
            return []

MANAGER = ProviderManager()
register = MANAGER.register_provider
unregister = MANAGER.unregister_provider

class ProviderHandler(object):
    def __init__(self, servicename):
        self.servicename = servicename
        event.add_callback(self._new_cb, "%s_provider_added"%servicename)
        event.add_callback(self._del_cb, "%s_provider_removed"%servicename)

    def _new_cb(self, name, obj, provider):
        self.on_new_provider(provider)

    def on_new_provider(self, provider):
        pass # for overriding

    def _del_cb(self, name, obj, provider):
        self.on_del_provider(provider)

    def on_del_provider(self, provider):
        pass # for overriding

    def get_providers(self):
        return MANAGER.get_providers(self.servicename)


# vim: et sts=4 sw=4

