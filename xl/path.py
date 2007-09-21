# Global path variables and methods
# Copyright (c) 2007 Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os

home = os.path.expanduser('~')
_configdir = os.path.join(home, '.exaile')
_cachedir = os.path.join(_configdir, 'cache')
_coverdir = os.path.join(_configdir, 'covers')

# These are set in init
_datadir = None
localedir = None
firstrun = None

def init(basedir, installed):
    global _datadir, localedir, firstrun

    if installed:
        prefix = os.path.normpath(os.path.join(basedir, '../..'))
        _datadir = os.path.join(prefix, 'share', 'exaile')
        localedir = os.path.join(prefix, 'share', 'locale')
    else:
        _datadir = basedir
        localedir = os.path.join(basedir, 'po')

    firstrun = not os.path.isdir(_configdir)
    if firstrun:
        try:
            os.mkdir(_configdir)
        except:
            # FIXME: Die?
            print "Could not create settings directory"
        try:
            os.mkdir(_cachedir)
        except:
            # FIXME: Die?
            print "Could not create cache directory"
        try:
            os.mkdir(_coverdir)
        except:
            # FIXME: Die?
            print "Could not create cover directory"

def set_configdir(dir):
    global _configdir
    _configdir = dir

def get_cache(*path_elems):
    return os.path.join(_cachedir, *path_elems)

def get_config(*path_elems):
    if path_elems[0] == 'cache':
        print "WARNING: get_config called for 'cache', use get_cache instead"
        import traceback
        traceback.print_stack()
    return os.path.join(_configdir, *path_elems)

def get_data(*path_elems):
    return os.path.join(_datadir, *path_elems)
