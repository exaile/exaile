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
import gtk, gtk.glade, gobject, sys, os, plugins, urllib
from xl import common, xlmisc
from gettext import gettext as _

def show_error(parent, message): 
    """
        Shows an error dialog
    """
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_OK, message)
    dialog.run()
    dialog.destroy()

class PluginManager(object):
    """
        Gui to manage plugins
    """
    def __init__(self, app, parent, manager, update, avail_url=''):
        """
            Initializes the manager
            params: parent window, plugin manager
        """
        self.app = app
        self.parent = parent
        self.update = update
        self.manager = manager
        self.fetched = False

        self.xml = gtk.glade.XML('plugins/plugins.glade',
            'PluginManagerDialog')
        self.dialog = self.xml.get_widget('PluginManagerDialog')
        self.dialog.set_transient_for(parent)
        self.plugin_nb = self.xml.get_widget('plugin_notebook')

        self.list = self.xml.get_widget('plugin_tree')
        self.version_label = self.xml.get_widget('version_label')
        self.author_label = self.xml.get_widget('author_label')
        self.name_label = self.xml.get_widget('name_label')
        self.description = self.xml.get_widget('description_view')
        self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, bool, object)
        self.xml.get_widget('ok_button').connect('clicked',
            lambda *e: self.dialog.destroy())
        self.configure_button = self.xml.get_widget('configure_button')
        self.configure_button.connect('clicked', self.configure_plugin)
        self.xml.get_widget('plugin_install_button').connect('clicked',
            self.install_plugin)

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Plugin")
        col.pack_start(pb, False)
        col.pack_start(text, False)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_fixed_width(1)
        col.set_expand(True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(text, text=1)

        self.list.append_column(col)

        text = gtk.CellRendererToggle()
        text.set_property('activatable', True)
        text.connect('toggled', self.toggle_cb, self.model)
        col = gtk.TreeViewColumn("Enabled", text)
        col.add_attribute(text, 'active', 2)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.list.append_column(col)

        for plugin in manager.plugins:
            icon = plugin.PLUGIN_ICON
            if not icon:
                icon = self.dialog.render_icon('gtk-execute', 
                    gtk.ICON_SIZE_MENU)
                
            self.model.append([icon, plugin.PLUGIN_NAME,
                plugin.PLUGIN_ENABLED, plugin])
    
        selection = self.list.get_selection()
        selection.connect('changed', self.row_selected)
        self.list.set_model(self.model)
        self.dialog.show_all()
        selection.select_path(0)

        if avail_url: 
            self.setup_avail_tab()
            self.avail_url = avail_url
            self.plugin_nb.connect('switch-page', self.check_fetch_avail)

    def install_plugin(self, *e):
        """
            Installs the selected plugin
        """
        selection = self.avail_list.get_selection()
        model, iter = selection.get_selected()
        if not iter: return
        file = model.get_value(iter, 5)
        self.download_plugin(file)

    @common.threaded
    def download_plugin(self, file):
        """
            Downloads the selected plugin 
        """
        download_dir = "%s%splugins" % (self.app.get_settings_dir(), os.sep)
        download_url = "http://www.exaile.org/trac/browser/plugins/%s/%s?format=txt" \
            % (self.app.get_plugin_location(), file)

        plugin = urllib.urlopen(download_url).read()
        h = open("%s%s%s" % (download_dir, os.sep, file), 'w')
        h.write(plugin)
        h.close()
        gobject.idle_add(common.info, self.parent, _("Your plugin has been "
            "installed.  You will need to restart Exaile to use it."))

    def check_fetch_avail(self, *e):
        """
            Checks to see if the available plugin list needs to be fetched
        """
        if not self.fetched:
            self.fetch_available_plugins(self.avail_url)
            xlmisc.log('Fetching available plugin list')
            self.fetched = True

    @common.threaded
    def fetch_available_plugins(self, url):
        """
            Fetches a plugin list from the specified url
        """
        h = urllib.urlopen(url)
        lines = h.readlines()
        h.close()
        gobject.idle_add(self.done_fetching, lines)

    def done_fetching(self, lines):

        for line in lines:
            line = line.strip()
            (file, name, version, author, description) = line.split('\t')
            description = description.replace("\n", " ").replace(r'\n', '\n')

            icon = self.dialog.render_icon('gtk-execute',
                gtk.ICON_SIZE_MENU)

            for plugin in self.manager.plugins:
                if plugin.PLUGIN_NAME == name and plugin.PLUGIN_ICON:
                    icon = plugin.PLUGIN_ICON
            self.avail_model.append([icon, name, version, author, description, file])

        selection = self.avail_list.get_selection()
        selection.select_path(0)
        self.avail_row_selected(selection)

    def setup_avail_tab(self):
        """
            Sets up the "plugins available" tab
        """
        self.avail_model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, str,
            str)
        self.avail_list = self.xml.get_widget('avail_plugin_tree')
        self.avail_version_label = self.xml.get_widget('avail_version_label')
        self.avail_author_label = self.xml.get_widget('avail_author_label')
        self.avail_name_label = self.xml.get_widget('avail_name_label')
        self.avail_description = self.xml.get_widget('avail_description_view')

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Plugin')
        col.pack_start(pb, False)
        col.pack_start(text, False)
#        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
#        col.set_fixed_width(1)
        col.set_expand(True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(text, text=1)
        self.avail_list.append_column(col)
        self.avail_list.set_model(self.avail_model)
        self.avail_description.get_buffer().set_text("Fetching available"
            " plugin list...")
        selection = self.avail_list.get_selection()
        selection.connect('changed', self.avail_row_selected)

    def avail_row_selected(self, selection):
        """
            Called when a user selects a row in the avialable tab
        """
        model, iter = selection.get_selected()
        if not iter: return

        name = model.get_value(iter, 1)
        version = model.get_value(iter, 2)
        author = model.get_value(iter, 3)
        description = model.get_value(iter, 4)

        self.avail_name_label.set_markup('<b>%s</b>' % name)
        self.avail_version_label.set_label(version)
        self.avail_author_label.set_label(author)
        self.avail_description.get_buffer().set_text(description)

    def toggle_cb(self, cell, path, model):
        """
            Called when the checkbox is toggled
        """
        plugin = model[path][3]
        model[path][2] = not model[path][2]
        plugin.PLUGIN_ENABLED = model[path][2]
        if plugin.PLUGIN_ENABLED:
            try:
                if not plugin.initialize():
                    PLUGIN_ENABLED = False
                    print "Error inizializing plugin"
                    model[path][2] = False
            except plugins.PluginInitException, e:
                show_error(self.parent, str(e))
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
               
    def row_selected(self, selection, user_data=None):
        """
            Called when a row is selected
        """
        (model, iter) = selection.get_selected()
        if not iter: return

        plugin = model.get_value(iter, 3)
        self.version_label.set_label(str(plugin.PLUGIN_VERSION))
        self.author_label.set_label(", ".join(plugin.PLUGIN_AUTHORS))
        self.description.get_buffer().set_text(plugin.PLUGIN_DESCRIPTION.replace(
            "\n", " ").replace(r'\n', "\n"))
        self.name_label.set_markup("<b>%s</b>" %
            common.escape_xml(plugin.PLUGIN_NAME))
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
