# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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


from xl import xdg, common, settings
import os, sys, imp, urllib, tarfile, shutil, traceback

import logging
logger = logging.getLogger(__name__)

# list of plugins to enable by default on new installs
DEFAULT_PLUGINS = ['shoutcast', 'amazoncovers',
    'lastfmdynamic', 'gnomemmkeys', 'lyricwiki',
    'cd']

class InvalidPluginError(Exception):
    pass

class PluginsManager(object):
    def __init__(self, exaile, load=True):
        self.plugindirs = [ os.path.join(p, 'plugins') \
                for p in xdg.get_data_dirs() ]
        
        for dir in self.plugindirs:
            try:
                os.makedirs(dir)
            except:
                pass

        self.plugindirs = [ x for x in self.plugindirs if os.path.exists(x) ]
        self.loaded_plugins = {}

        self.exaile = exaile 
        self.enabled_plugins = {}
        self.settings = settings.SettingsManager.settings
        
        if load: self.load_enabled()

    def __findplugin(self, pluginname):
        for dir in self.plugindirs:
            if os.path.exists(os.path.join(dir, pluginname)):
                return os.path.join(dir, pluginname)
        return None

    def load_plugin(self, pluginname, reload=False):
        if not reload and pluginname in self.loaded_plugins:
            return self.loaded_plugins[pluginname]

        path = self.__findplugin(pluginname)
        if path is None:
            return False
        sys.path.insert(0, path)
        plugin = imp.load_source(pluginname, os.path.join(path,'__init__.py'))
        sys.path = sys.path[1:]
        self.loaded_plugins[pluginname] = plugin
        return plugin

    def install_plugin(self, path):
        tar = tarfile.open(path, "r:*") #transparently supports gz, bz2

        #ensure the paths in the archive are sane
        mems = tar.getmembers()
        base = os.path.basename(path)[:-4]
        for m in mems:
            if not m.name.startswith(base):
                raise InvalidPluginError("Plugin archive contains an unsafe path")

        tar.extractall(self.plugindirs[0])

    def uninstall_plugin(self, pluginname):
        self.disable_plugin(pluginname)
        for dir in self.plugindirs:
            try:
                shutil.rmtree(self.__findplugin(pluginname))
                return True
            except:
                pass
        return False

    def enable_plugin(self, pluginname):
        try:
            plugin = self.load_plugin(pluginname)
            if not plugin: raise Exception("Error loading plugin")
            plugin.enable(self.exaile)
            self.enabled_plugins[pluginname] = plugin
            logger.debug("Loaded plugin %s"%pluginname)
        except:
            traceback.print_exc()
            logger.warning("Unable to enable plugin %s"%pluginname)
            common.log_exception(logger)
            return False
        return True

    def disable_plugin(self, pluginname):
        try:
            plugin = self.enabled_plugins[pluginname]
            plugin.disable(self.exaile)
            del self.enabled_plugins[pluginname]
        except:
            traceback.print_exc()
            logger.warning("Unable to fully disable plugin %s"%pluginname)
            common.log_exception(logger)
            return False
        return True

    def list_installed_plugins(self):
        pluginlist = []
        for dir in self.plugindirs:
            if os.path.exists(dir):
                for file in os.listdir(dir):
                    if file not in pluginlist and \
                            os.path.isdir(os.path.join(dir, file)):
                        pluginlist.append(file)
        return pluginlist

    def list_available_plugins(self):
        pass

    def list_updateable_plugins(self):
        pass

    def get_plugin_info(self, pluginname):
        path = os.path.join(self.__findplugin(pluginname), 'PLUGININFO')
        f = open(path)
        infodict = {}
        for line in f:
            try:
                key, val = line.split("=",1)
                infodict[key] = eval(val)
            except ValueError:
                pass # this happens on blank lines
        return infodict

    def save_enabled(self):
        self.settings.set_option("plugins/enabled", self.enabled_plugins.keys())

    def load_enabled(self):
        to_enable = self.settings.get_option("plugins/enabled", DEFAULT_PLUGINS)
        for plugin in to_enable:
            self.enable_plugin(plugin)

# vim: et sts=4 sw=4

