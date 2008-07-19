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

import os

homedir = os.getenv("HOME")
lastdir = homedir

data_home = os.getenv("XDG_DATA_HOME")
if data_home == None:
    data_home = os.path.join(homedir, ".local", "share")
data_home = os.path.join(data_home, "exaile")
if not os.path.exists(data_home):
    os.makedirs(data_home)

config_home = os.getenv("XDG_CONFIG_HOME")
if config_home == None:
    config_home = os.path.join(homedir, ".config")
config_home = os.path.join(config_home, "exaile")
if not os.path.exists(config_home):
    os.makedirs(config_home)

cache_home = os.getenv("XDG_CACHE_HOME")
if cache_home == None:
    cache_home = os.path.join(homedir, ".cache")
cache_home = os.path.join(cache_home, "exaile")
if not os.path.exists(cache_home):
    os.makedirs(cache_home)

data_dirs = os.getenv("XDG_DATA_DIRS")
if data_dirs == None:
    data_dirs = "/usr/local/share/:/usr/share/"
data_dirs = [ os.path.join(dir, "exaile") for dir in data_dirs.split(":") ]

exaile_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
if os.path.exists(os.path.join(exaile_dir, 'Makefile')): #hack
    data_dirs.insert(0, os.path.join(exaile_dir, 'data'))

data_dirs.insert(0, data_home)

def get_config_dir():
    return config_home

def get_data_dirs():
    return data_dirs[:]

def get_cache_dir():
    return cache_home

def get_data_path(subpath):
    for dir in data_dirs:
        path = os.path.join(dir, subpath)
        if os.path.exists(path):
            return path
    return None

def get_last_dir():
    return lastdir

# vim: et sts=4 sw=4

