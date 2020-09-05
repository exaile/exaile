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

import importlib.util
import inspect
import logging
import os
import shutil
import sys
import tarfile

from xl.nls import gettext as _
from xl import event, settings, xdg

logger = logging.getLogger(__name__)


class InvalidPluginError(Exception):
    def __str__(self):
        return str(self.args[0])


class PluginsManager:
    def __init__(self, exaile, load=True):
        self.plugindirs = [os.path.join(p, 'plugins') for p in xdg.get_data_dirs()]
        if xdg.local_hack:
            self.plugindirs.insert(1, os.path.join(xdg.exaile_dir, 'plugins'))

        try:
            os.makedirs(self.plugindirs[0])
        except Exception:
            pass

        self.plugindirs = [x for x in self.plugindirs if os.path.exists(x)]
        self.loaded_plugins = {}

        self.exaile = exaile
        self.enabled_plugins = {}

        self.load = load

    def __findplugin(self, pluginname):
        for plugin_dir in self.plugindirs:
            path = os.path.join(plugin_dir, pluginname)
            if os.path.exists(path):
                return path
        return None

    def load_plugin(self, pluginname, reload_plugin=False):
        if not reload_plugin and pluginname in self.loaded_plugins:
            return self.loaded_plugins[pluginname]

        path = self.__findplugin(pluginname)
        if path is None:
            return False

        spec = importlib.util.spec_from_file_location(
            pluginname, os.path.join(path, '__init__.py')
        )
        plugin = importlib.util.module_from_spec(spec)
        # We need to temporarily add the plugin to sys.modules because otherwise the loader will fail to exec_module() if the plugin uses relative imports.
        if pluginname in sys.modules:
            raise InvalidPluginError(
                _('Plugin is already loaded or has a conflicting name.')
            )
        sys.modules[pluginname] = plugin
        spec.loader.exec_module(plugin)
        sys.modules[pluginname] = None

        if hasattr(plugin, 'plugin_class'):
            plugin = plugin.plugin_class()
        self.loaded_plugins[pluginname] = plugin
        return plugin

    def install_plugin(self, path):
        try:
            tar = tarfile.open(path, "r:*")  # transparently supports gz, bz2
        except (tarfile.ReadError, OSError):
            raise InvalidPluginError(_('Plugin archive is not in the correct format.'))

        # ensure the paths in the archive are sane
        mems = tar.getmembers()
        base = os.path.basename(path).split('.')[0]
        if os.path.isdir(os.path.join(self.plugindirs[0], base)):
            raise InvalidPluginError(
                _('A plugin with the name "%s" is already installed.') % base
            )

        for m in mems:
            if not m.name.startswith(base):
                raise InvalidPluginError(_('Plugin archive contains an unsafe path.'))

        tar.extractall(self.plugindirs[0])

    def __on_new_plugin_loaded(self, eventname, exaile, maybe_name, fn):
        event.remove_callback(self.__on_new_plugin_loaded, eventname)
        fn()

    def __enable_new_plugin(self, plugin):
        '''Sets up a new-style plugin. See helloworld plugin for details'''

        if hasattr(plugin, 'on_gui_loaded'):
            if self.exaile.loading:
                event.add_ui_callback(
                    self.__on_new_plugin_loaded,
                    'gui_loaded',
                    None,
                    plugin.on_gui_loaded,
                )
            else:
                plugin.on_gui_loaded()

        if hasattr(plugin, 'on_exaile_loaded'):
            if self.exaile.loading:
                event.add_ui_callback(
                    self.__on_new_plugin_loaded,
                    'exaile_loaded',
                    None,
                    plugin.on_exaile_loaded,
                )
            else:
                plugin.on_exaile_loaded()

    def uninstall_plugin(self, pluginname):
        self.disable_plugin(pluginname)
        for plugin_dir in self.plugindirs:
            try:
                shutil.rmtree(self.__findplugin(pluginname))
                return True
            except Exception:
                pass
        return False

    def enable_plugin(self, pluginname):
        try:
            plugin = self.load_plugin(pluginname)
            if not plugin:
                raise Exception("Error loading plugin")
            plugin.enable(self.exaile)
            if not inspect.ismodule(plugin):
                self.__enable_new_plugin(plugin)
            self.enabled_plugins[pluginname] = plugin
            logger.debug("Loaded plugin %s", pluginname)
            self.save_enabled()
            event.log_event('plugin_enabled', self, pluginname)
        except Exception as e:
            logger.exception("Unable to enable plugin %s", pluginname)
            raise e

    def disable_plugin(self, pluginname):
        try:
            plugin = self.enabled_plugins[pluginname]
            del self.enabled_plugins[pluginname]
        except KeyError:
            logger.exception("Plugin not found, possibly already disabled")
            return False
        try:
            plugin.disable(self.exaile)
            logger.debug("Unloaded plugin %s", pluginname)
            self.save_enabled()
        except Exception as e:
            logger.exception("Unable to fully disable plugin %s", pluginname)
            raise e
        finally:
            event.log_event('plugin_disabled', self, pluginname)
        return True

    def list_installed_plugins(self):
        pluginlist = []
        for directory in self.plugindirs:
            if not os.path.exists(directory):
                continue
            for name in os.listdir(directory):
                if (
                    name == '__pycache__'
                    or name in pluginlist
                    or not os.path.exists(os.path.join(directory, name, 'PLUGININFO'))
                ):
                    continue
                pluginlist.append(name)
        return pluginlist

    def list_available_plugins(self):
        pass

    def list_updateable_plugins(self):
        pass

    def get_plugin_info(self, pluginname):
        path = os.path.join(self.__findplugin(pluginname), 'PLUGININFO')
        infodict = {}
        with open(path) as f:
            for line in f:
                try:
                    key, val = line.split("=", 1)
                    # restricted eval - no bult-in funcs. marginally more secure.
                    infodict[key] = eval(val, {'__builtins__': None, '_': _}, {})
                except ValueError:
                    pass  # this happens on blank lines
        return infodict

    def is_compatible(self, info):
        """
        Returns True if the plugin claims to be compatible with the
        current platform.

        :param info: The data returned from get_plugin_info()
        """
        platforms = info.get('Platforms', [])
        if len(platforms) == 0:
            platforms = [sys.platform]

        for platform in platforms:
            if sys.platform.startswith(platform):
                return True

        return False

    def is_potentially_broken(self, info):
        """
        Returns True if one of the modules that the plugin requires is
        not detected as available.

        :param info: The data returned from get_plugin_info()
        """
        import pkgutil
        from gi.repository import GIRepository

        gir = GIRepository.Repository.get_default()

        modules = info.get('RequiredModules', [])

        for module in modules:
            pair = module.split(':', 1)
            if len(pair) > 1:
                prefix, module = pair
                if prefix == 'gi':
                    if not gir.enumerate_versions(module):
                        return True
            else:
                if not pkgutil.find_loader(module):
                    return True

        return False

    def save_enabled(self):
        if self.load:
            settings.set_option("plugins/enabled", list(self.enabled_plugins.keys()))

    def load_enabled(self):
        to_enable = settings.get_option("plugins/enabled", [])
        for plugin in to_enable:
            try:
                self.enable_plugin(plugin)
            except Exception:
                pass

    def teardown(self, main):
        """
        Tears down all enabled plugins
        """
        for plugin_name, plugin in self.enabled_plugins.items():
            if hasattr(plugin, 'teardown'):
                try:
                    plugin.teardown(main)
                except Exception:
                    logger.exception("Unable to tear down plugin %s", plugin_name)


# vim: et sts=4 sw=4
