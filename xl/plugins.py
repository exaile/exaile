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

import imp
import inspect
import logging
import os
import shutil
import sys
import tarfile
import traceback

from xl.nls import gettext as _
from xl import xdg, common, settings

logger = logging.getLogger(__name__)

class InvalidPluginError(Exception):
    def __str__(self):
        return str(self.args[0])

class PluginsManager(object):
    def __init__(self, exaile, load=True):
        self.plugindirs = [ os.path.join(p, 'plugins') \
                for p in xdg.get_data_dirs() ]
        if xdg.local_hack:
            self.plugindirs.insert(1, os.path.join(xdg.exaile_dir, 'plugins'))

        for dir in self.plugindirs:
            try:
                os.makedirs(dir)
            except:
                pass

        self.plugindirs = [ x for x in self.plugindirs if os.path.exists(x) ]
        self.loaded_plugins = {}

        self.exaile = exaile
        self.enabled_plugins = {}

        self.load = load

        if self.load:
            self.load_enabled()

    def __findplugin(self, pluginname):
        for dir in self.plugindirs:
            path = os.path.join(dir, pluginname)
            if os.path.exists(path):
                return path
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
        try:
            tar = tarfile.open(path, "r:*") #transparently supports gz, bz2
        except (tarfile.ReadError, OSError):
            raise InvalidPluginError(
                _('Plugin archive is not in the correct format.'))

        #ensure the paths in the archive are sane
        mems = tar.getmembers()
        base = os.path.basename(path).split('.')[0]
        if os.path.isdir(os.path.join(self.plugindirs[0], base)):
            raise InvalidPluginError(
                _('A plugin with the name "%s" is already installed.') % base)

        for m in mems:
            if not m.name.startswith(base):
                raise InvalidPluginError(
                    _('Plugin archive contains an unsafe path.'))

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
            logger.debug("Loaded plugin %s" % pluginname)
            self.save_enabled()
        except Exception, e:
            traceback.print_exc()
            logger.warning("Unable to enable plugin %s" % pluginname)
            common.log_exception(logger)
            raise e

    def disable_plugin(self, pluginname):
        try:
            plugin = self.enabled_plugins[pluginname]
            del self.enabled_plugins[pluginname]
            plugin.disable(self.exaile)
            logger.debug("Unloaded plugin %s" % pluginname)
            self.save_enabled()
        except Exception, e:
            traceback.print_exc()
            logger.warning("Unable to fully disable plugin %s" % pluginname)
            common.log_exception(logger)
            raise e

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
                # restricted eval - no bult-in funcs. marginally more secure.
                infodict[key] = eval(val, {'__builtins__': None, '_': _}, {})
            except ValueError:
                pass # this happens on blank lines
        return infodict

    def get_plugin_default_preferences(self, pluginname):
        """
            Returns the default preferences for a plugin
        """
        preflist = {}
        path = self.__findplugin(pluginname)
        plugin = imp.load_source(pluginname, os.path.join(path,'__init__.py'))
        try:
            preferences_pane = plugin.get_preferences_pane()
            for c in dir(preferences_pane):
                attr = getattr(preferences_pane, c)
                if inspect.isclass(attr):
                    try:
                        preflist[attr.name] = attr.default
                    except AttributeError:
                        pass
        except AttributeError:
            pass
        return preflist

    def save_enabled(self):
        if self.load:
            settings.set_option("plugins/enabled", self.enabled_plugins.keys())

    def load_enabled(self):
        to_enable = settings.get_option("plugins/enabled", [])
        for plugin in to_enable:
            try:
                self.enable_plugin(plugin)
            except:
                pass

# vim: et sts=4 sw=4

