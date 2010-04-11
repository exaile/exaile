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

import os, glib

homedir = os.path.expanduser("~")
lastdir = homedir

data_home = glib.get_user_data_dir()
data_home = os.path.join(data_home, "exaile")
if not os.path.exists(data_home):
    os.makedirs(data_home)

config_home = glib.get_user_config_dir()
config_home = os.path.join(config_home, "exaile")
if not os.path.exists(config_home):
    os.makedirs(config_home)

cache_home = glib.get_user_cache_dir()
cache_home = os.path.join(cache_home, "exaile")
if not os.path.exists(cache_home):
    os.makedirs(cache_home)

data_dirs = os.getenv("XDG_DATA_DIRS")
if data_dirs == None:
    data_dirs = "/usr/local/share/:/usr/share/"
data_dirs = [os.path.join(d, "exaile") for d in data_dirs.split(":")]

config_dirs = os.getenv("XDG_CONFIG_DIRS")
if config_dirs == None:
    config_dirs = "/etc/xdg"
config_dirs = [os.path.join(d, "exaile") for d in config_dirs.split(":")]

exaile_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
local_hack = False
# Detect if Exaile is not installed.
if os.path.exists(os.path.join(exaile_dir, 'Makefile')):
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
    return config_dirs

def get_data_dir():
    return data_home

def get_data_dirs():
    return data_dirs[:]

def get_cache_dir():
    return cache_home


def _get_path(basedirs, *subpath_elements):
    subpath = os.path.join(*subpath_elements)
    for d in basedirs:
        path = os.path.join(d, subpath)
        if os.path.exists(path):
            return path
    return None

def get_data_path(*subpath_elements):
    return _get_path(data_dirs, *subpath_elements)

def get_config_path(*subpath_elements):
    return _get_path(config_dirs, *subpath_elements)

def get_data_home_path(*subpath_elements):
    return _get_path([data_home], *subpath_elements)

def get_last_dir():
    return lastdir

def get_plugin_data_dir():
    path = os.path.join(get_data_dirs()[0], 'plugin_data')
    if not os.path.exists(path):
        os.makedirs(path)
    return path

# vim: et sts=4 sw=4

