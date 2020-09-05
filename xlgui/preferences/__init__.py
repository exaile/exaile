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

import inspect
import locale
import logging

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from xl import xdg
from xl.nls import gettext as _
from xlgui import icons
from . import (
    appearance,
    collection,
    cover,
    lyrics,
    playback,
    playlists,
    plugin,
    widgets,
)

logger = logging.getLogger(__name__)


class PreferencesDialog:
    """
    Preferences Dialog
    """

    PAGES = (playlists, appearance, playback, collection, cover, lyrics)
    PREFERENCES_DIALOG = None

    def __init__(self, parent, main):
        """
        Initializes the preferences dialog
        """
        self.main = main
        self.last_child = None
        self.last_page = None
        self.parent = parent
        self.fields = {}
        self.panes = {}
        self.builders = {}
        self.popup = None

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain('exaile')
        self.builder.add_from_file(
            xdg.get_data_path('ui', 'preferences', 'preferences_dialog.ui')
        )
        self.builder.connect_signals(self)

        self.window = self.builder.get_object('PreferencesDialog')
        self.window.set_transient_for(parent)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.window.connect('delete-event', lambda *e: self.close())

        self.box = self.builder.get_object('preferences_box')

        self.tree = self.builder.get_object('preferences_tree')
        self.model = self.builder.get_object('model')

        title_cellrenderer = self.builder.get_object('title_cellrenderer')
        title_cellrenderer.props.ypad = 3

        self.default_icon = icons.MANAGER.pixbuf_from_icon_name(
            'document-properties', Gtk.IconSize.MENU
        )

        # sets up the default panes
        for page in self.PAGES:
            icon = self.default_icon

            if hasattr(page, 'icon'):
                if isinstance(page.icon, GdkPixbuf.Pixbuf):
                    icon = page.icon
                else:
                    icon = icons.MANAGER.pixbuf_from_icon_name(
                        page.icon, Gtk.IconSize.MENU
                    )

            self.model.append(None, [page, page.name, icon])

        # Use icon name to allow overrides
        plugin_icon = icons.MANAGER.pixbuf_from_icon_name(
            'extension', Gtk.IconSize.MENU
        )
        self.plug_root = self.model.append(None, [plugin, _('Plugins'), plugin_icon])

        self._load_plugin_pages()

        selection = self.tree.get_selection()
        selection.connect('changed', self.switch_pane)
        # Disallow selection on rows with no widget to show
        selection.set_select_function(
            (lambda sel, model, path, issel, dat: model[path][0] is not None), None
        )

        GLib.idle_add(selection.select_path, (0,))

    def _load_plugin_pages(self):
        self._clear_children(self.plug_root)
        plugin_pages = []
        plugin_manager = self.main.exaile.plugins

        for name in plugin_manager.enabled_plugins:
            plugin = plugin_manager.enabled_plugins[name]
            if hasattr(plugin, 'get_preferences_pane'):
                try:
                    plugin_pages.append(plugin.get_preferences_pane())
                except Exception:
                    logger.exception('Error loading preferences pane')

        plugin_pages.sort(key=lambda x: locale.strxfrm(x.name))

        for page in plugin_pages:
            icon = self.default_icon

            if hasattr(page, 'icon'):
                if isinstance(page.icon, GdkPixbuf.Pixbuf):
                    icon = page.icon
                else:
                    icon = icons.MANAGER.pixbuf_from_icon_name(
                        page.icon, Gtk.IconSize.MENU
                    )

            self.model.append(self.plug_root, [page, page.name, icon])

        GLib.idle_add(self.tree.expand_row, self.model.get_path(self.plug_root), False)

    def _clear_children(self, node):
        remove = []
        iter = self.model.iter_children(node)
        while iter:
            remove.append(iter)
            iter = self.model.iter_next(iter)

        for iter in remove:
            self.model.remove(iter)

    def on_close_button_clicked(self, widget):
        """
        Called when the user clicks 'ok'
        """
        self.close()

    def close(self):
        """
        Closes the preferences dialog
        """
        if hasattr(self.last_page, 'page_leave'):
            self.last_page.page_leave(self)
        self.window.hide()
        self.window.destroy()
        PreferencesDialog.PREFERENCES_DIALOG = None

    def switch_pane(self, selection):
        """
        Switches a pane
        """
        (model, iter) = selection.get_selected()
        if not iter:
            return
        page = self.model.get_value(iter, 0)
        if not page:
            return

        if self.last_child:
            self.box.remove(self.last_child)

        if self.last_page:
            if hasattr(self.last_page, 'page_leave'):
                self.last_page.page_leave(self)

        self.last_page = page

        child = self.panes.get(page)
        if not child:
            if hasattr(page, 'ui'):
                builder = Gtk.Builder()
                builder.add_from_file(page.ui)
            else:
                logger.error("No preference pane found")
                return

            child = builder.get_object('preferences_pane')
            init = getattr(page, 'init', None)
            if init:
                init(self, builder)
            self.panes[page] = child
            self.builders[page] = builder

        if page not in self.fields:
            self._populate_fields(page, self.builders[page])

        if hasattr(page, 'page_enter'):
            page.page_enter(self)

        child.unparent()
        self.box.pack_start(child, True, True, 0)
        self.last_child = child
        self.box.show_all()

    def _populate_fields(self, page, builder):
        """
        Populates field pages
        """
        self.fields[page] = []

        attributes = dir(page)

        for attr in attributes:
            try:
                klass = getattr(page, attr)

                if inspect.isclass(klass) and issubclass(klass, widgets.Preference):
                    widget = builder.get_object(klass.name)

                    if not widget:
                        logger.warning('Invalid preferences widget: %s', klass.name)
                        continue

                    if issubclass(klass, widgets.Conditional):
                        klass.condition_widget = builder.get_object(
                            klass.condition_preference_name
                        )
                    elif issubclass(klass, widgets.MultiConditional):
                        for name in klass.condition_preference_names:
                            klass.condition_widgets[name] = builder.get_object(name)

                    field = klass(self, widget)

                    label_widget = builder.get_object('label:%s' % klass.name)
                    if label_widget:
                        field.label_widget = label_widget

                    self.fields[page].append(field)
            except Exception:
                logger.exception('Broken preferences class: %s', attr)

    def run(self):
        """
        Runs the dialog
        """
        if PreferencesDialog.PREFERENCES_DIALOG:
            self = PreferencesDialog.PREFERENCES_DIALOG
            self.window.present()
        else:
            PreferencesDialog.PREFERENCES_DIALOG = self
            self.window.show_all()


# vim: et sts=4 sw=4
