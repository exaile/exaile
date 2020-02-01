# Copyright (C) 2010 Adam Olsen
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

from gi.repository import Gtk
from xl import providers


class Accelerator:
    __slots__ = ['name', 'keys', 'helptext', 'callback', 'key', 'mods']

    def __init__(self, keys, helptext, callback):
        self.name = keys  # only here because providers needs it
        self.keys = keys
        self.helptext = helptext
        self.callback = callback
        self.key, self.mods = Gtk.accelerator_parse(keys)


class AcceleratorManager(providers.ProviderHandler):
    def __init__(self, providername, accelgroup):
        self.accelgroup = accelgroup
        self.accelerators = {}
        providers.ProviderHandler.__init__(self, providername, simple_init=True)

    def on_provider_added(self, provider):
        self.accelgroup.connect(
            provider.key, provider.mods, Gtk.AccelFlags.VISIBLE, provider.callback
        )

        # Add accelerator to internal list, so we can enable and disable
        # them via enable_accelerators() and disable_accelerators()
        self.accelerators[(provider.key, provider.mods)] = provider

    def on_provider_removed(self, provider):
        self.accelgroup.disconnect_key(provider.key, provider.mods)

        # Remove accelerator from our internal list
        del self.accelerators[(provider.key, provider.mods)]

    ## Global accelerator enable/disable
    def disable_accelerators(self):
        for provider in self.accelerators.values():
            self.accelgroup.disconnect_key(provider.key, provider.mods)

    def enable_accelerators(self):
        for provider in self.accelerators.values():
            self.accelgroup.connect(
                provider.key, provider.mods, Gtk.AccelFlags.VISIBLE, provider.callback
            )
