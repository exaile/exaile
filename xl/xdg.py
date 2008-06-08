

import os

homedir = os.getenv("HOME")

data_home = os.getenv("XDG_DATA_HOME")
if data_home == None:
    data_home = os.path.join(homedir, ".local", "share")
data_home = os.path.join(data_home, "exaile")
if not os.path.exists(data_home):
    os.mkdir(data_home)

config_home = os.getenv("XDG_CONFIG_HOME")
if config_home == None:
    config_home = os.path.join(homedir, ".config")
config_home = os.path.join(config_home, "exaile")
if not os.path.exists(config_home):
    os.mkdir(config_home)

data_dirs = os.getenv("XDG_DATA_DIRS")
if data_dirs == None:
    data_dirs = "/usr/local/share/:/usr/share/"
data_dirs = [ os.path.join(dir, "exaile") for dir in data_dirs.split(":") ]
data_dirs.insert(0, data_home)

def get_config_dir():
    return config_home

def get_data_dirs():
    return data_dirs


# vim: et sts=4 sw=4

