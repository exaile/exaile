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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

from gi.repository import GLib
from gi.repository import Gtk

import xl.unicode
from xl import event, main, plugins, xdg
from xlgui.widgets import common, dialogs
from xl.nls import gettext as _, ngettext

import logging

logger = logging.getLogger(__name__)

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
            parent=builder.get_object('preferences_pane'), buttons=Gtk.ButtonsType.CLOSE
        )
        self.message.connect('response', self.on_messagebar_response)

        self.list = builder.get_object('plugin_tree')
        self.enabled_cellrenderer = builder.get_object('enabled_cellrenderer')

        if main.exaile().options.Debug:
            reload_cellrenderer = common.ClickableCellRendererPixbuf()
            reload_cellrenderer.props.icon_name = 'view-refresh'
            reload_cellrenderer.props.xalign = 1
            reload_cellrenderer.connect('clicked', self.on_reload_cellrenderer_clicked)

            name_column = builder.get_object('name_column')
            name_column.pack_start(reload_cellrenderer, True)
            name_column.add_attribute(reload_cellrenderer, 'visible', 3)

        self.version_label = builder.get_object('version_label')
        self.author_label = builder.get_object('author_label')
        self.name_label = builder.get_object('name_label')
        self.description = builder.get_object('description_view')

        self.model = builder.get_object('model')
        self.filter_model = self.model.filter_new()

        self.show_incompatible_cb = builder.get_object('show_incompatible_cb')

        self.filter_model.set_visible_func(self._model_visible_func)

        selection = self.list.get_selection()
        selection.connect('changed', self.on_selection_changed)
        self._load_plugin_list()

        self._evt_rm1 = event.add_ui_callback(
            self.on_plugin_event, 'plugin_enabled', None, True
        )
        self._evt_rm2 = event.add_ui_callback(
            self.on_plugin_event, 'plugin_disabled', None, False
        )
        self.list.connect('destroy', self.on_destroy)

        GLib.idle_add(selection.select_path, (0,))
        GLib.idle_add(self.list.grab_focus)

    def _load_plugin_list(self):
        """
            Loads the plugin list
        """
        plugins = self.plugins.list_installed_plugins()
        uncategorized = _('Uncategorized')
        plugins_dict = {uncategorized: []}
        failed_list = []

        self.plugin_to_path = {}

        for plugin_name in plugins:
            try:
                info = self.plugins.get_plugin_info(plugin_name)

                compatible = self.plugins.is_compatible(info)
                broken = self.plugins.is_potentially_broken(info)

            except Exception:
                failed_list += [plugin_name]
                continue

            # determine icon to show
            if not compatible:
                icon = 'dialog-error'
            elif broken:
                icon = 'dialog-warning'
            else:
                icon = None

            enabled = plugin_name in self.plugins.enabled_plugins
            plugin_data = (
                plugin_name,
                info['Name'],
                str(info['Version']),
                enabled,
                icon,
                broken,
                compatible,
                True,
            )

            if 'Category' in info:
                cat = plugins_dict.setdefault(info['Category'], [])
                cat.append(plugin_data)
            else:
                plugins_dict[uncategorized].append(plugin_data)

        self.list.set_model(None)
        self.model.clear()

        def categorykey(item):
            if item[0] == uncategorized:
                return '\xff' * 10
            return xl.unicode.strxfrm(item[0])

        plugins_dict = sorted(plugins_dict.iteritems(), key=categorykey)

        for category, plugins_list in plugins_dict:
            plugins_list.sort(key=lambda x: xl.unicode.strxfrm(x[1]))

            it = self.model.append(
                None, (None, category, '', False, '', False, True, False)
            )

            for plugin_data in plugins_list:
                pit = self.model.append(it, plugin_data)
                path = self.model.get_string_from_iter(pit)
                self.plugin_to_path[plugin_data[0]] = path

        self.list.set_model(self.filter_model)

        # TODO: Keep track of which categories are already expanded, and only expand those
        self.list.expand_all()

        if failed_list:
            self.message.show_error(
                _('Could not load plugin info!'),
                ngettext('Failed plugin: %s', 'Failed plugins: %s', len(failed_list))
                % ', '.join(failed_list),
            )

    def on_destroy(self, widget):
        self._evt_rm1()
        self._evt_rm2()

    def on_messagebar_response(self, widget, response):
        """
            Hides the messagebar if requested
        """
        if response == Gtk.ResponseType.CLOSE:
            widget.hide()

    def on_plugin_tree_row_activated(self, tree, path, column):
        """
            Enables or disables the selected plugin
        """
        self.enabled_cellrenderer.emit('toggled', path[0])

    def on_reload_cellrenderer_clicked(self, cellrenderer, path):
        """
            Reloads a plugin from scratch
        """
        plugin_name = self.filter_model[path][0]
        enabled = self.filter_model[path][3]

        if enabled:
            try:
                self.plugins.disable_plugin(plugin_name)
            except Exception as e:
                self.message.show_error(_('Could not disable plugin!'), str(e))
                return

        logger.info('Reloading plugin %s...', plugin_name)
        self.plugins.load_plugin(plugin_name, reload_plugin=True)

        if enabled:
            try:
                self.plugins.enable_plugin(plugin_name)
            except Exception as e:
                self.message.show_error(_('Could not enable plugin!'), str(e))
                return

    def on_install_plugin_button_clicked(self, button):
        """
            Shows a dialog allowing the user to choose a plugin to install
            from the filesystem
        """
        dialog = Gtk.FileChooserDialog(
            _('Choose a Plugin'),
            self.preferences.parent,
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_ADD,
                Gtk.ResponseType.OK,
            ),
        )

        filter = Gtk.FileFilter()
        filter.set_name(_('Plugin Archives'))
        filter.add_pattern("*.exz")
        filter.add_pattern("*.tar.gz")
        filter.add_pattern("*.tar.bz2")
        dialog.add_filter(filter)

        filter = Gtk.FileFilter()
        filter.set_name(_('All Files'))
        filter.add_pattern('*')
        dialog.add_filter(filter)

        result = dialog.run()
        dialog.hide()

        if result == Gtk.ResponseType.OK:
            try:
                self.plugins.install_plugin(dialog.get_filename())
            except plugins.InvalidPluginError as e:
                self.message.show_error(_('Plugin file installation failed!'), str(e))

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

        if not row[7]:
            self.author_label.set_label('')
            self.description.get_buffer().set_text('')
            self.name_label.set_label('')
            return

        info = self.plugins.get_plugin_info(row[0])

        self.author_label.set_label(",\n".join(info['Authors']))

        self.description.get_buffer().set_text(info['Description'].replace(r'\n', "\n"))

        self.name_label.set_markup(
            "<b>%s</b> <small>%s</small>" % (info['Name'], info['Version'])
        )

    def on_enabled_cellrenderer_toggled(self, cellrenderer, path):
        """
            Called when the checkbox is toggled
        """
        path = Gtk.TreePath.new_from_string(path)
        plugin_name = self.filter_model[path][0]
        if plugin_name is None:
            return

        enable = not self.filter_model[path][3]

        if enable:
            try:
                self.plugins.enable_plugin(plugin_name)
            except Exception as e:
                self.message.show_error(_('Could not enable plugin!'), str(e))
                return
        else:
            try:
                self.plugins.disable_plugin(plugin_name)
            except Exception as e:
                self.message.show_error(_('Could not disable plugin!'), str(e))
                return

        self.on_selection_changed(self.list.get_selection())

    def on_plugin_event(self, evtname, obj, plugin_name, enabled):

        if hasattr(self.plugins.loaded_plugins[plugin_name], 'get_preferences_pane'):
            self.preferences._load_plugin_pages()

        path = self.plugin_to_path[plugin_name]
        self.model[path][3] = enabled

    def on_show_incompatible_cb_toggled(self, widget):
        self.filter_model.refilter()

    def _model_visible_func(self, model, iter, data):
        row = model[iter]
        compatible = row[6]
        return compatible or self.show_incompatible_cb.get_active()


def init(preferences, xml):
    PluginManager(preferences, xml)
