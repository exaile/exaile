# Copyright (C) 2008-2010 Adam Olsen
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

import glib
import gobject
import gtk
import locale

from xlgui.preferences import widgets
from xl import main, plugins, xdg
from xlgui.widgets import dialogs
from xl.nls import gettext as _, ngettext

name = _('Plugins')
ui = xdg.get_data_path('ui', 'preferences', 'plugin.ui')

class PluginManager(object):
    """
        Gui to manage plugins
    """
    def __init__(self, preferences, builder):
        """
            Initializes the manager
        """
        self.preferences = preferences
        builder.connect_signals(self)
        self.plugins = main.exaile().plugins

        self.message = dialogs.MessageBar(
            parent=builder.get_object('preferences_pane'),
            buttons=gtk.BUTTONS_CLOSE
        )
        self.message.connect('response', self.on_messagebar_response)

        self.list = builder.get_object('plugin_tree')
        self.enabled_cellrenderer = builder.get_object('enabled_cellrenderer')

        self.version_label = builder.get_object('version_label')
        self.author_label = builder.get_object('author_label')
        self.name_label = builder.get_object('name_label')
        self.description = builder.get_object('description_view')
        self.model = builder.get_object('model')

        selection = self.list.get_selection()
        selection.connect('changed', self.on_selection_changed)
        self._load_plugin_list()
        glib.idle_add(selection.select_path, (0,))
        glib.idle_add(self.list.grab_focus)

    def _load_plugin_list(self):
        """
            Loads the plugin list
        """
        plugins = self.plugins.list_installed_plugins()
        plugins_list = []
        failed_list = []

        for plugin in plugins:
            try:
                info = self.plugins.get_plugin_info(plugin)
            except Exception, e:
                failed_list += [plugin]
                continue

            enabled = plugin in self.plugins.enabled_plugins
            plugins_list.append((plugin, info['Name'], info['Version'], enabled))

        plugins_list.sort(key=lambda x: locale.strxfrm(x[1]))

        self.list.set_model(None)
        self.model.clear()

        for plugin in plugins_list:
            self.model.append(plugin)

        self.list.set_model(self.model)

        if failed_list:
            self.message.show_error(_('Could not load plugin info!'),
                ngettext(
                    'Failed plugin: %s',
                    'Failed plugins: %s',
                    len(failed_list)
                ) % ', '.join(failed_list)
            )

    def on_messagebar_response(self, widget, response):
        """
            Hides the messagebar if requested
        """
        if response == gtk.RESPONSE_CLOSE:
            widget.hide()

    def on_plugin_tree_row_activated(self, tree, path, column):
        """
            Enables or disables the selected plugin
        """
        self.enabled_cellrenderer.emit('toggled', path[0])

    def on_install_plugin_button_clicked(self, button):
        """
            Shows a dialog allowing the user to choose a plugin to install
            from the filesystem
        """
        dialog = gtk.FileChooserDialog(_('Choose a Plugin'),
            self.preferences.parent,
            buttons=(
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_ADD, gtk.RESPONSE_OK
            )
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
                self.message.show_error(
                    _('Plugin file installation failed!'), str(e))

                return

            self._load_plugin_list()

    def on_selection_changed(self, selection, user_data=None):
        """
            Called when a row is selected
        """
        model, paths = selection.get_selected_rows()
        if not paths:
            return

        row = model[paths[0]]

        info = self.plugins.get_plugin_info(row[0])

        self.author_label.set_label(",\n".join(info['Authors']))

        self.description.get_buffer().set_text(
            info['Description'].replace(r'\n', "\n"))

        self.name_label.set_markup("<b>%s</b>" % info['Name'])

    def on_enabled_cellrenderer_toggled(self, cellrenderer, path):
        """
            Called when the checkbox is toggled
        """
        plugin = self.model[path][0]
        enable = not self.model[path][3]

        if enable:
            try:
                self.plugins.enable_plugin(plugin)
            except Exception, e:
                self.message.show_error(_('Could not enable plugin!'), str(e))
                return
        else:
            try:
                self.plugins.disable_plugin(plugin)
            except Exception, e:
                self.message.show_error(_('Could not disable plugin!'), str(e))
                return

        if hasattr(self.plugins.loaded_plugins[plugin],
            'get_preferences_pane'):
            self.preferences._load_plugin_pages()

        self.model[path][3] = enable
        self.on_selection_changed(self.list.get_selection())

def init(preferences, xml):
    manager = PluginManager(preferences, xml)
