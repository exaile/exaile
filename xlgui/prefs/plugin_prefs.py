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

import locale
import gtk, gobject
from xlgui.prefs import widgets
from xl import main, plugins, xdg
from xlgui import commondialogs
from xl.nls import gettext as _

name = _('Plugins')
ui = xdg.get_data_path('ui/plugin_prefs_pane.glade')

class PluginManager(object):
    """
        Gui to manage plugins
    """
    def __init__(self, prefs, builder):
        """
            Initializes the manager
        """
        self.prefs = prefs
        self.builder = builder
        self.plugins = main.exaile().plugins

        self.list = self.builder.get_object('plugin_tree')
        #self.configure_button = self.builder.get_object('configure_button')

        self.version_label = self.builder.get_object('version_label')
        self.author_label = self.builder.get_object('author_label')
        self.name_label = self.builder.get_object('name_label')
        self.description = self.builder.get_object('description_view')
        self.model = gtk.ListStore(str, str, bool, object)

        self._connect_signals()
        self._setup_tree()
        self._load_plugin_list()
        self.list.get_selection().select_path((0,))

    def _load_plugin_list(self):
        """
            Loads the plugin list
        """
        plugins = self.plugins.list_installed_plugins()

        plugins_list = []
        for plugin in plugins:
            try:
                info = self.plugins.get_plugin_info(plugin)
            except IOError:
                continue
            enabled = plugin in self.plugins.enabled_plugins
            plugins_list.append((info['Name'], info['Version'], enabled,
                plugin))
        plugins_list.sort(key=lambda x: locale.strxfrm(x[0]))

        for plugin in plugins_list:
            self.model.append(plugin)

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

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Version'), text, text=1)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)

        self.list.append_column(col)

        text = gtk.CellRendererToggle()
        text.set_property('activatable', True)
        text.connect('toggled', self.toggle_cb, self.model)
        col = gtk.TreeViewColumn(_('Enabled'), text)
        col.add_attribute(text, 'active', 2)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.list.append_column(col)

        selection = self.list.get_selection()
        selection.connect('changed', self.row_selected)

    def _connect_signals(self):
        """
            Connects signals
        """
        self.builder.connect_signals({
            'on_install_plugin_button_clicked': lambda *e:
                self.choose_plugin_dialog(),
        })

    def choose_plugin_dialog(self):
        """
            Shows a dialog allowing the user to choose a plugin to install
            from the filesystem
        """
        dialog = gtk.FileChooserDialog(_('Choose a plugin'),
            self.prefs.parent,
            buttons=(
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_ADD, gtk.RESPONSE_OK)
            )

        filter = gtk.FileFilter()
        filter.set_name(_('Plugin Archives'))
        filter.add_pattern("*.exz")
        filter.add_pattern("*.tar.gz")
        filter.add_pattern("*.tar.bz2")
        dialog.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name(_('All Files'))
        filter.add_pattern('*')
        dialog.add_filter(filter)

        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_OK:
            try:
                self.plugins.install_plugin(dialog.get_filename())
            except plugins.InvalidPluginError, e:
                commondialogs.error(self.builder.get_object('PreferencesDialog'), e.message)
                return

            self._load_plugin_list()

    def row_selected(self, selection, user_data=None):
        """
            Called when a row is selected
        """
        (model, iter) = selection.get_selected()
        if not iter: return

        pluginname = model.get_value(iter, 3)
        info = self.plugins.get_plugin_info(pluginname)
        self.author_label.set_label(",\n".join(info['Authors']))
        self.description.get_buffer().set_text(
            info['Description'].replace(r'\n', "\n"))
        self.name_label.set_markup("<b>%s</b>" % info['Name'])
        (model, iter) = selection.get_selected()
        pluginname = model.get(iter, 2)[0]
        #if self.__configure_available(pluginname):
        #    self.configure_button.set_sensitive(True)
        #else:
        #    self.configure_button.set_sensitive(False)

    def toggle_cb(self, cell, path, model):
        """
            Called when the checkbox is toggled
        """
        plugin = model[path][3]
        enable = not model[path][2]

        if enable:
            try:
                self.plugins.enable_plugin(plugin)
            except Exception, e:
                commondialogs.error(self.builder.get_object('PreferencesDialog'), _('Could '
                    'not enable plugin: %s') % str(e))
                return
        else:
            try:
                self.plugins.disable_plugin(plugin)
            except Exception, e:
                commondialogs.error(self.builder.get_object('PreferencesDialog'), _('Could '
                    'not disable plugin: %s') % str(e))
                return

        if hasattr(self.plugins.loaded_plugins[plugin],
            'get_prefs_pane'):
            self.prefs._load_plugin_pages()
        model[path][2] = enable
        self.row_selected(self.list.get_selection())

def init(prefs, xml):
    manager = PluginManager(prefs, xml)
