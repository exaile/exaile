


from xl import xdg, common
import os, imp

import logging
logger = logging.getLogger(__name__)

class PluginsManager(object):
    def __init__(self, exaile):
        self.plugindirs = [ os.path.join(p, 'plugins') \
                for p in xdg.get_data_dirs() ]
        
        for dir in self.plugindirs:
            try:
                os.makedirs(dir)
            except:
                pass

        self.exaile = exaile 
        
        self.loaded_plugins = {}

        self.enabled_plugins = {}

    def load_installed_plugins(self):
        for plugin in self.list_installed_plugins:
            self.load_plugin(plugin)

    def __findplugin(self, pluginname):
        for dir in self.plugindirs:
            if os.path.exists(os.path.join(dir, pluginname)):
                return os.path.join(dir, pluginname)
        return None

    def load_plugin(self, pluginname):
        path = self.__findplugin(pluginname)
        if path is None:
            return False
        plugin = imp.load_source(pluginname, os.path.join(path,'__init__.py'))
        self.loaded_plugins[pluginname] = plugin
        logger.debug("Loaded plugin %s"%pluginname)
        return True

    def install_plugin(self, uri):
        pass

    def uninstall_plugin(self, pluginname):
        pass

    def enable_plugin(self, pluginname):
        try:
            plugin = self.loaded_plugins[pluginname]
            plugin.enable(self.exaile)
            self.enabled_plugins[pluginname] = plugin
        except:
            logger.warning("Unable to enable plugin %s."%pluginname)
            common.log_exception()
            return False
        return True

    def disable_plugin(self, pluginname):
        try:
            plugin = self.enabled_plugins[pluginname]
            plugin.disable(self.exaile)
            del self.enabled_plugins[pluginname]
        except:
            logger.warning("Unable to fully disable plugin %s."%pluginname)
            common.log_exception()
            return False
        return True

    def list_installed_plugins(self):
        pluginlist = []
        for dir in self.plugindirs:
            if os.path.exists(dir):
                for file in os.listdir(dir):
                    if file not in pluginlist:
                        pluginlist.append(file)
        return pluginlist

    def list_available_plugins(self):
        pass

    def list_updateable_plugins(self):
        pass

    
    def save_enabled(self):
        pass

    def load_enabled(self):
        pass
