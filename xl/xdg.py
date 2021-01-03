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

import os
import sys
from gi.repository import GLib

# exaile_dir is now defined in xl.version, but most of the codebase
# still accessed it via xl.xdg.exaile_dir
from .version import exaile_dir

homedir = os.path.expanduser("~")
lastdir = homedir

data_home = GLib.get_user_data_dir()
data_home = os.path.join(data_home, "exaile")

config_home = GLib.get_user_config_dir()
config_home = os.path.join(config_home, "exaile")

cache_home = GLib.get_user_cache_dir()
cache_home = os.path.join(cache_home, "exaile")

if sys.platform == 'win32':
    logs_home = os.path.join(data_home, "logs")
else:
    logs_home = os.path.join(cache_home, "logs")

data_dirs = os.getenv("XDG_DATA_DIRS")
if data_dirs is None:
    if sys.platform == 'win32':
        data_dirs = [exaile_dir]
    else:
        data_dirs = ["/usr/local/share/exaile", "/usr/share/exaile"]
else:
    data_dirs = [os.path.join(d, "exaile") for d in data_dirs.split(os.pathsep)]

config_dirs = os.getenv("XDG_CONFIG_DIRS")
if config_dirs is None:
    if sys.platform == 'win32':
        config_dirs = [exaile_dir]
    else:
        config_dirs = ["/usr/local/etc/xdg/exaile", "/etc/xdg/exaile"]
else:
    config_dirs = [os.path.join(d, "exaile") for d in config_dirs.split(os.pathsep)]

local_hack = False
# Detect if Exaile is not installed.
if os.path.exists(os.path.join(exaile_dir, 'data')):
    local_hack = True
    # Insert the "data" directory to data_dirs.
    data_dir = os.path.join(exaile_dir, 'data')
    data_dirs.insert(0, data_dir)
    # insert the config dir
    config_dir = os.path.join(exaile_dir, 'data', 'config')
    config_dirs.insert(0, config_dir)


data_dirs.insert(0, data_home)


def get_config_dir():
    return config_home


def get_config_dirs():
    return config_dirs[:]


def get_data_dir():
    return data_home


def get_data_dirs():
    return data_dirs[:]


def get_cache_dir():
    return cache_home


def get_logs_dir():
    return logs_home


def _get_path(basedirs, *subpath_elements, **kwargs):
    check_exists = kwargs.get("check_exists", True)
    subpath = os.path.join(*subpath_elements)
    for d in basedirs:
        path = os.path.join(d, subpath)
        if not check_exists or os.path.exists(path):
            return path
    return None


def get_data_path(*subpath_elements, **kwargs):
    return _get_path(data_dirs, *subpath_elements, **kwargs)


def get_config_path(*subpath_elements, **kwargs):
    return _get_path(config_dirs, *subpath_elements, **kwargs)


def get_data_home_path(*subpath_elements, **kwargs):
    return _get_path([data_home], *subpath_elements, **kwargs)


def get_last_dir():
    return lastdir


def get_plugin_data_dir():
    path = os.path.join(get_data_dirs()[0], 'plugin_data')
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def _make_missing_dirs():
    """
    Make any missing base XDG directories

    called by the main Exaile object, should not be used elsewhere.
    """
    if not os.path.exists(data_home):
        os.makedirs(data_home)
    if not os.path.exists(config_home):
        os.makedirs(config_home)
    if not os.path.exists(cache_home):
        os.makedirs(cache_home)
    if not os.path.exists(logs_home):
        os.makedirs(logs_home)


# vim: et sts=4 sw=4
