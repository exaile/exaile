#!/usr/bin/env python

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

import pygtk, manager
pygtk.require('2.0')
import gtk, gtk.glade, gobject, sys, os

class PluginManager(object):
    """
        Gui to manage plugins
    """
    def __init__(self, parent, manager, update):
        """
            Initializes the manager
            params: parent window, plugin manager
        """
        self.parent = parent
        self.update = update
        self.manager = manager

        self.xml = gtk.glade.XML('plugins/plugins.glade',
            'PluginManagerDialog')
        self.dialog = self.xml.get_widget('PluginManagerDialog')
        self.dialog.set_transient_for(parent)

        self.list = self.xml.get_widget('plugin_tree')
        self.version_label = self.xml.get_widget('version_label')
        self.author_label = self.xml.get_widget('author_label')
        self.name_label = self.xml.get_widget('name_label')
        self.description = self.xml.get_widget('description_view')
        self.list.connect('button-release-event', self.row_selected)
        self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, bool, object)
        self.xml.get_widget('ok_button').connect('clicked',
            lambda *e: self.dialog.destroy())
        self.configure_button = self.xml.get_widget('configure_button')
        self.configure_button.connect('clicked', self.configure_plugin)

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Plugin")
        col.pack_start(pb, False)
        col.pack_start(text, False)
        col.set_fixed_width(152)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_resizable(True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(text, text=1)

        self.list.append_column(col)

        text = gtk.CellRendererToggle()
        text.set_property('activatable', True)
        text.connect('toggled', self.toggle_cb, self.model)
        col = gtk.TreeViewColumn("", text)
        col.add_attribute(text, 'active', 2)
        self.list.append_column(col)

        for plugin in manager.plugins:
            icon = plugin.PLUGIN_ICON
            if not icon:
                icon = self.dialog.render_icon('gtk-execute', 
                    gtk.ICON_SIZE_MENU)
                
            self.model.append([icon, plugin.PLUGIN_NAME,
                plugin.PLUGIN_ENABLED, plugin])
    
        selection = self.list.get_selection()
        self.list.set_model(self.model)
        self.dialog.show_all()
        selection.select_path(0)
        self.row_selected()

    def toggle_cb(self, cell, path, model):
        """
            Called when the checkbox is toggled
        """
        plugin = model[path][3]
        model[path][2] = not model[path][2]
        plugin.PLUGIN_ENABLED = model[path][2]
        if plugin.PLUGIN_ENABLED:
            if not plugin.initialize(self.manager.parent):
                PLUGIN_ENABLED = False
                print "Error inizializing plugin"
                model[path][2] = False
        else:
            plugin.destroy()
            plugin.PLUGIN_ENABLED = False

        print "Plugin %s set to enabled: %s" % (plugin.PLUGIN_NAME, 
            plugin.PLUGIN_ENABLED)
        if self.update:
            self.update(plugin)

    def configure_plugin(self, *e):
        """
            Calls the plugin's configure function
        """
        selection = self.list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter: return

        plugin = model.get_value(iter, 3)
        plugin.configure()
               
    def row_selected(self, *e):
        """
            Called when a row is selected
        """
        selection = self.list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter: return

        plugin = model.get_value(iter, 3)
        self.version_label.set_label(str(plugin.PLUGIN_VERSION))
        self.author_label.set_label(", ".join(plugin.PLUGIN_AUTHORS))
        self.description.get_buffer().set_text(plugin.PLUGIN_DESCRIPTION.replace(
            "\n", " ").replace(r'\n', "\n"))
        self.name_label.set_markup("<b>%s</b>" % plugin.PLUGIN_NAME)
        self.configure_button.set_sensitive(hasattr(plugin, 'configure'))

class PluginTest(object):
    def __init__(self, name, version, author, desc):
        self.PLUGIN_NAME = name
        self.PLUGIN_VERSION = version
        self.PLUGIN_AUTHORS = [author]
        self.PLUGIN_DESCRIPTION = desc
        self.PLUGIN_ICON = None
        self.PLUGIN_ENABLED = True


# testing
if __name__ == '__main__':
    manager = manager.Manager(None)
    manager.plugins.append(PluginTest('fruit', 1.0, 'arolsen@gmail.com',
        'fags'))

    m = PluginManager(None, manager)
    gtk.main()
