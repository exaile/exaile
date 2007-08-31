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

import os, re, traceback, sys, zipimport
import xl.plugins

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
        if not os.path.isdir(dir): return
        for file in os.listdir(dir):
            if file.endswith('.py') or file.endswith('.exz'):
                self.initialize_plugin(dir, file, enabled)

    def import_zip(self, dir, file):
        modname = file.replace('.exz', '')
        zip = zipimport.zipimporter(os.path.join(dir, file))
        plugin = zip.load_module(modname)
        plugin.ZIP = zip
        if hasattr(plugin, 'load_data'):
            plugin.load_data(zip)
            
        return plugin

    def initialize_plugin(self, dir, file, enabled=None, upgrading=False):
        try:
            if file.endswith('.exz'):
                plugin = self.import_zip(dir, file)
                if not plugin: return
            else:
                oldpath = sys.path
                try:
                    sys.path.insert(0, dir)
                    plugin = __import__(re.sub('\.pyc?$', '', file))
                finally:
                    sys.path = oldpath

            if not hasattr(plugin, "PLUGIN_NAME"):
                return

            if not hasattr(plugin, "PLUGIN_ENABLED"):
                plugin.PLUGIN_ENABLED = False

            if plugin.PLUGIN_NAME in self.loaded and upgrading: return
            if not upgrading:
                # check to see if this plugin is already installed and remove
                # it if that's the case
                for p in self.plugins:
                    if p.PLUGIN_NAME == plugin.PLUGIN_NAME:
                        p.destroy()
                        self.plugins.remove(p)

                if plugin.PLUGIN_NAME in self.loaded:
                    self.loaded.remove(plugin.PLUGIN_NAME)

            self.loaded.append(plugin.PLUGIN_NAME)
            
            print "Plugins '%s' version '%s' loaded successfully" % \
                (plugin.PLUGIN_NAME, plugin.PLUGIN_VERSION)

            plugin.FILE_NAME = file.replace('.exz', '.py')
            plugin.APP = self.app
           
            file = file.replace('.exz', '.py')
            if (enabled is None or file in enabled) or plugin.PLUGIN_ENABLED:
                if plugin.initialize():
                    plugin.PLUGIN_ENABLED = True
            self.plugins.append(plugin)
        except xl.plugins.PluginInitException, e:
            self.plugins.append(plugin)
        except Exception, e:
            print "Failed to load plugin"
            traceback.print_exc()
