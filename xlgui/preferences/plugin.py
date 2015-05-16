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

import glib
import gobject
import gtk
import locale
import logging

from xlgui.preferences import widgets
from xl import main, plugins, xdg
from xlgui.widgets import common, dialogs
from xl.nls import gettext as _, ngettext

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
            parent=builder.get_object('preferences_pane'),
            buttons=gtk.BUTTONS_CLOSE
        )
        self.message.connect('response', self.on_messagebar_response)

        self.list = builder.get_object('plugin_tree')
        self.enabled_cellrenderer = builder.get_object('enabled_cellrenderer')

        if main.exaile().options.Debug:
            reload_cellrenderer = common.ClickableCellRendererPixbuf()
            reload_cellrenderer.props.stock_id = gtk.STOCK_REFRESH
            reload_cellrenderer.props.xalign = 1
            reload_cellrenderer.connect('clicked',
                self.on_reload_cellrenderer_clicked)

            name_column = builder.get_object('name_column')
            name_column.pack_start(reload_cellrenderer)
            name_column.add_attribute(reload_cellrenderer, 'visible', 3)

        self.version_label = builder.get_object('version_label')
        self.author_label = builder.get_object('author_label')
        self.name_label = builder.get_object('name_label')
        self.description = builder.get_object('description_view')
        
        self.model = builder.get_object('model')
        self.filter_model = self.model.filter_new()
        
        self.show_incompatible_cb = builder.get_object('show_incompatible_cb')
        self.show_broken_cb = builder.get_object('show_broken_cb')
        
        self.filter_model.set_visible_func(self._model_visible_func)
        
        self.status_column = builder.get_object('status_column')
        self._set_status_visible()

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
        uncategorized = _('Uncategorized')
        plugins_dict = { uncategorized: [] }
        failed_list = []

        for plugin in plugins:
            try:
                info = self.plugins.get_plugin_info(plugin)
                
                compatible = self.plugins.is_compatible(info)    
                broken = self.plugins.is_potentially_broken(info)
                
            except Exception, e:
                failed_list += [plugin]
                continue
            
            # determine icon to show
            if broken or not compatible:
                icon = gtk.STOCK_DIALOG_WARNING
            else:
                icon = gtk.STOCK_APPLY

            enabled = plugin in self.plugins.enabled_plugins
            plugin_data = (plugin, info['Name'], str(info['Version']),
                           enabled, icon, broken, compatible, True)
            
            if 'Category' in info:
                if info['Category'] in plugins_dict:
                    plugins_dict[info['Category']].append(plugin_data)
                else:
                    plugins_dict[info['Category']] = [plugin_data]
            else:
                plugins_dict[uncategorized].append(plugin_data)

        

        self.list.set_model(None)
        self.model.clear()
        
        plugins_dict = sorted(plugins_dict.iteritems(), key=lambda x: 'zzzz' if x[0] == uncategorized else locale.strxfrm(x[0]))

        for category, plugins_list in plugins_dict:
            plugins_list.sort(key=lambda x: locale.strxfrm(x[1]))
        
            it = self.model.append(None, (None, category, '', False, '', False, True, False))
        
            for plugin in plugins_list:
                self.model.append(it, plugin)

        self.list.set_model(self.filter_model)
        
        # TODO: Keep track of which categories are already expanded, and only expand those
        self.list.expand_all()
        
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

    def on_reload_cellrenderer_clicked(self, cellrenderer, path):
        """
            Reloads a plugin from scratch
        """
        plugin = self.filter_model[path][0]
        enabled = self.filter_model[path][3]

        if enabled:
            try:
                self.plugins.disable_plugin(plugin)
            except Exception, e:
                self.message.show_error(_('Could not disable plugin!'), str(e))
                return

        logger.info('Reloading plugin %s...' % plugin)
        self.plugins.load_plugin(plugin, reload=True)

        if enabled:
            try:
                self.plugins.enable_plugin(plugin)
            except Exception, e:
                self.message.show_error(_('Could not enable plugin!'), str(e))
                return

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

        if not row[7]:
            self.author_label.set_label('')
            self.description.get_buffer().set_text('')
            self.name_label.set_label('')
            return
        
        info = self.plugins.get_plugin_info(row[0])

        self.author_label.set_label(",\n".join(info['Authors']))

        self.description.get_buffer().set_text(
            info['Description'].replace(r'\n', "\n"))

        self.name_label.set_markup("<b>%s</b>" % info['Name'])

    def on_enabled_cellrenderer_toggled(self, cellrenderer, path):
        """
            Called when the checkbox is toggled
        """
        plugin = self.filter_model[path][0]
        if plugin is None:
            return
        
        enable = not self.filter_model[path][3]

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
        
        self.model[self.filter_model.convert_path_to_child_path(path)][3] = enable
        self.on_selection_changed(self.list.get_selection())
        
    def on_show_broken_cb_toggled(self, widget):
        self._set_status_visible()
        self.filter_model.refilter()
        
    def on_show_incompatible_cb_toggled(self, widget):
        self._set_status_visible()
        self.filter_model.refilter()
        
    def _set_status_visible(self):
        show_col = self.show_broken_cb.get_active() or \
                   self.show_incompatible_cb.get_active()
        self.status_column.set_visible(show_col)
        
    def _model_visible_func(self, model, iter, data):
        
        row = model[iter]
        broken = row[5]
        compatible = row[6]
        
        show = not broken or self.show_broken_cb.get_active()
        compatible = compatible or self.show_incompatible_cb.get_active()
        
        result = compatible and show
        
        return result
            

def init(preferences, xml):
    manager = PluginManager(preferences, xml)
