# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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
import os, gtk
from xl import common

def name(file):
    return os.path.basename(file.replace('.pyc', '.py'))

class Plugin(object):
    """
        Base object for plugins
    """
    def __init__(self):
        """
            Initializes the plugin
        """
        pass

    def initialize(self):
        pass

    def destroy(self):
        pass

class SignalContainer(object):
    def __init__(self):
        self.dict = {}

    def connect(self, obj, signal, func, *args):
        try:
            conns = self.dict[obj]
        except KeyError:
            conns = self.dict[obj] = []
        conns.append(obj.connect(signal, func, *args))

    def disconnect_object(self, obj):
        conns = self.dict.get(obj, None)
        if conns:
            for conn in conns:
                obj.disconnect(conn)
            del self.dict[obj]

    def disconnect_all(self):
        for obj, conns in self.dict.iteritems():
            for conn in conns:
                obj.disconnect(conn)
        self.dict = {}

class PluginConfigDialog(gtk.Dialog):
    """
        A generic plugin configuration dialog
    """
    def __init__(self, parent, plugin):
        """
            Initializes the dialog
        """
        gtk.Dialog.__init__(self, "Plugin Configuration", parent)
        self.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)
        self.add_button("gtk-ok", gtk.RESPONSE_OK)

        self.main = self.child
        self.main.set_spacing(3)

        label = gtk.Label("<b>%s Configuration</b>" %
            common.escape_xml(plugin))
        label.set_markup(label.get_label())
        self.main.pack_start(label, False, False)

class PluginInitException(Exception):
    """
        Called when a plugin can't be enabled
    """
    def __init__(self, message):
        Exception.__init__(self, message)

class DeviceDriver(object):
    def get_initial_root(self, model):
        return None

    def connect(self):
        return True

    def search_tracks(self):
        return []

    def disconnect(self):
        pass

    def get_item(self):
        pass
