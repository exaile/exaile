#!/usr/bin/env python

import gtk, gobject, time, urllib
from gettext import gettext as _
from xl import common, xlmisc
import xl.plugins as plugins

PLUGIN_NAME = _("Update Notifier")
PLUGIN_AUTHORS = ['Adam Olsen <arolsen' + chr(32+32) + 'gmail' + '.com>']
PLUGIN_VERSION = "0.3.2"
PLUGIN_DESCRIPTION = _(r"""Notifies the user of Exaile and plugin updates""")

PLUGIN_ENABLED = False
PLUGIN_ICON = None
PLUGIN = None
APP = None

def found_updates(found):
    message = _("The following plugins have new versions available for install."
    " You can install them from the plugin manager.\n\n")

    for (name, version) in found:
        message += "%s\t%s\n" % (name, version)

    common.info(APP.window, message)

@common.threaded
def start_thread(exaile):
    # check exaile itself
    version = map(int, APP.get_version().replace('svn', '').split('.'))
    check_version = map(int,
        urllib.urlopen('http://exaile.org/current_version.txt').read().split('.'))

    if version < check_version:
        gobject.idle_add(common.info, APP.window, _("Exaile version %s is "
            "available.  Grab it from http://www.exaile.org today!") % 
            '.'.join([str(i) for i in check_version]))

    # check plugins
    pmanager = APP.pmanager
    avail_url = 'http://www.exaile.org/files/plugins/%s/plugin_info.txt' % \
            APP.get_plugin_location()

    h = urllib.urlopen(avail_url)
    lines = h.readlines()
    h.close()

    found = []

    check = False
    for line in lines:
        line = line.strip()
        (file, name, version, author, description) = line.split('\t')
        
        for plugin in pmanager.plugins:
            if plugin.PLUGIN_NAME == name:
                installed_ver = map(int, plugin.PLUGIN_VERSION.split('.'))
                available_ver = map(int, version.split('.'))

                if installed_ver < available_ver:
                    found.append((name, version))

    if found:
        gobject.idle_add(found_updates, found)

def initialize():
    """
    Connect to the PluginEvents
    """
    global SIGNAL_ID
    SIGNAL_ID = APP.playlist_manager.connect('last-playlist-loaded', start_thread)

    return True

def destroy():
    global SIGNAL_ID
    if SIGNAL_ID:
        gobject.source_remove(SIGNAL_ID)
