# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import os, re, traceback, sys, plugins

class Manager(object):
    """
        Plugin manager. 
        Manages loading plugins, and sending events to them
    """
    def __init__(self, app):
        """
            Initializes the manager
        """
        self.plugins = []
        self.app = app
        self.loaded = []

    def load_plugins(self, dir, enabled):
        """
            Loads all plugins in a specified directory
        """
        if not dir in sys.path: sys.path.append(dir)
        if not os.path.isdir(dir): return
        for file in os.listdir(dir):
            if file.endswith('.py'):
                try:
                    plugin = __import__(re.sub('\.pyc?$', '', file))
                    if not hasattr(plugin, "PLUGIN_NAME"):
                        continue

                    if plugin.PLUGIN_NAME in self.loaded: continue
                    self.loaded.append(plugin.PLUGIN_NAME)
                    
                    print "Plugins '%s' version '%s' loaded successfully" % \
                        (plugin.PLUGIN_NAME, plugin.PLUGIN_VERSION)

                    plugin.FILE_NAME = file
                    plugin.APP = self.app
                    if file in enabled or plugin.PLUGIN_ENABLED:
                        if plugin.initialize():
                            plugin.PLUGIN_ENABLED = True
                    self.plugins.append(plugin)
                except plugins.PluginInitException, e:
                    self.plugins.append(plugin)
                except Exception, e:
                    print "Failed to load plugin"
                    traceback.print_exc()

    def fire_event(self, event):
        """
            Fires an event to all plugins
        """
        check = True
        for plugin in self.plugins:
            if not plugin.PLUGIN_ENABLED: continue
            for method, args in event.calls.iteritems():
                if not hasattr(plugin, method): continue
                func = getattr(plugin, method)
                if func and callable(func):
                    if not func(*args):
                        check = False
        return check
