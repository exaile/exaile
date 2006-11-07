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

import os, re, traceback, sys

class Manager(object):
    """
        Plugin manager. 
        Manages loading plugins, and sending events to them
    """
    def __init__(self, parent):
        """
            Initializes the manager
        """
        self.plugins = []
        self.parent = parent

    def load_plugins(self, dir, enabled):
        """
            Loads all plugins in a specified directory
        """
        if not dir in sys.path: sys.path.append(dir)
        if not os.path.isdir(dir): return
        for file in os.listdir(dir):
            if file.endswith('.py'):
                try:
                    print "Attempting to load plugin: %s" % file

                    plugin = __import__(re.sub('\.pyc?$', '', file))
                    if not getattr(plugin, "PLUGIN_NAME"):
                        print "%s is not a plugin, skipping" % file
                        continue

                    if not plugin.initialize(self.parent): continue
                    self.plugins.append(plugin)
                    print "Plugin %s, version %s inizilaized" % \
                        (plugin.PLUGIN_NAME, plugin.PLUGIN_VERSION)
                    plugin.FILE_NAME = file.replace('.pyc', '.py')
                    if file.replace(".pyc", ".py") in enabled:
                        plugin.PLUGIN_ENABLED = True
                except Exception, e:
                    print "Failed to load plugin"
                    traceback.print_exc()

    def fire_event(self, event):
        """
            Fires an event to all plugins
        """
        for plugin in self.plugins:
            if not plugin.PLUGIN_ENABLED: continue
            for method, args in event.calls.iteritems():
                if not hasattr(plugin, method): continue
                func = getattr(plugin, method)
                if func and callable(func):
                    func(*args)
