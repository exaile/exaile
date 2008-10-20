# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

from xl import xdg
from xl.nls import gettext as _
import gtk, gtk.glade

class PluginManager(object):
    """
        Gui to manage plugins
    """
    def __init__(self, parent, plugins):
        """
            Initializes the manager
        """
        self.parent = parent
        self.plugins = plugins

        self.xml = gtk.glade.XML(
            xdg.get_data_path('glade/plugin_dialog.glade'),
            'PluginManagerDialog', 'exaile')

        self.dialog = self.xml.get_widget('PluginManagerDialog')
        self.dialog.set_transient_for(parent)

        self.list = self.xml.get_widget('plugin_tree')

        self.version_label = self.xml.get_widget('version_label')
        self.author_label = self.xml.get_widget('author_label')
        self.name_label = self.xml.get_widget('name_label')
        self.description = self.xml.get_widget('description_view')
        self.model = gtk.ListStore(str, bool, object)

        self._connect_signals()
        self._setup_tree()
        self._load_plugin_list()

    def _load_plugin_list(self):
        """
            Loads the plugin list
        """
        plugins = self.plugins.list_installed_plugins()
        plugins.sort()

        for plugin in plugins:
            info = self.plugins.get_plugin_info(plugin)
            enabled = plugin in self.plugins.enabled_plugins.keys()
            self.model.append([info['Name'], enabled, plugin])

        self.list.set_model(self.model)

    def _setup_tree(self):
        """
            Sets up the tree view for plugins
        """
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Plugin'), text, text=0)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_fixed_width(1)
        col.set_expand(True)

        self.list.append_column(col)

        text = gtk.CellRendererToggle()
        text.set_property('activatable', True)
        text.connect('toggled', self.toggle_cb, self.model)
        col = gtk.TreeViewColumn(_('Enabled'), text)
        col.add_attribute(text, 'active', 1)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.list.append_column(col)

        selection = self.list.get_selection()
        selection.connect('changed', self.row_selected)

    def _connect_signals(self):
        """
            Connects signals
        """
        self.xml.signal_autoconnect({
            'on_close_button_clicked':  lambda *e: self.destroy(),
        })

    def row_selected(self, selection, user_data=None):
        """
            Called when a row is selected
        """
        (model, iter) = selection.get_selected()
        if not iter: return

        pluginname = model.get_value(iter, 2)
        info = self.plugins.get_plugin_info(pluginname)
        self.version_label.set_label(info['Version'])
        self.author_label.set_label(", ".join(info['Authors']))
        self.description.get_buffer().set_text(
            info['Description'].replace(r'\n', "\n"))
        self.name_label.set_markup("<b>%s</b>" % info['Name'])

    def run(self):
        return self.dialog.run()

    def toggle_cb(self, cell, path, model):
        """
            Called when the checkbox is toggled
        """
        plugin = model[path][2]
        enable = model[path][1] = not model[path][1]

        if enable:
            self.plugins.enable_plugin(plugin)
        else:
            self.plugins.disable_plugin(plugin)

    def destroy(self, *e):
        self.dialog.destroy()
