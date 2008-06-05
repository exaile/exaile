# mostly depreciated, use xdg.py instead

import os
from xl import common

home = os.path.expanduser(u'~')
_configdir = os.path.join(home, '.exaile-0.3')
_cachedir = os.path.join(_configdir, 'cache')

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
            common.log("Could not create settings directory")
        try:
            os.mkdir(_cachedir)
        except:
            # FIXME: Die?
            common.log("Could not create cache directory")

def set_configdir(dir):
    global _configdir, _cachedir
    _configdir = dir
    _cachedir = os.path.join(_configdir, 'cache')

def get_cache(*path_elems):
    return os.path.join(_cachedir, *path_elems)

def get_config(*path_elems):
    if path_elems[0] == 'cache':
        common.log("WARNING: get_config called for 'cache', "
            "use get_cache instead")
    return os.path.join(_configdir, *path_elems)

def get_data(*path_elems):
    return os.path.join(_datadir, *path_elems)
