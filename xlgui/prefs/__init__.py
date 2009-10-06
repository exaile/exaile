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

import thread, os, shlex, string, urllib2
from xl.nls import gettext as _
import inspect
import pygtk
pygtk.require('2.0')
import gtk
from xl import xdg
from xl.settings import _SETTINGSMANAGER
from xlgui.prefs.widgets import *
from xlgui.prefs import playlists_prefs, osd_prefs, collection_prefs
from xlgui.prefs import cover_prefs, playback_prefs, appearance_prefs
from xlgui.prefs import plugin_prefs
import logging, traceback, gobject

logger = logging.getLogger(__name__)

class PreferencesDialog(object):
    """
        Preferences Dialog
    """

    PAGES = (playlists_prefs, appearance_prefs, playback_prefs, 
        collection_prefs, osd_prefs, cover_prefs)
    PREFERENCES_DIALOG = None

    def __init__(self, parent, main):
        """
            Initializes the preferences dialog
        """
        self.main = main
        self.last_child = None
        self.last_page = None
        self.parent = parent
        self.settings = _SETTINGSMANAGER
        self.plugins = self.main.exaile.plugins.list_installed_plugins()
        self.fields = {} 
        self.panes = {}
        self.builders = {}
        self.popup = None

        self.builder = gtk.Builder()
        self.builder.set_translation_domain('exaile')
        self.builder.add_from_file(
            xdg.get_data_path('ui/preferences_dialog.glade'))

        self.window = self.builder.get_object('PreferencesDialog')
        self.window.set_transient_for(parent)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.connect('delete-event', lambda *e: self.cancel())

        self._connect_events()

        self.box = self.builder.get_object('prefs_box')

        self.tree = self.builder.get_object('prefs_tree')
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Preferences'), text, text=0)
        self.tree.append_column(col)

        self.model = gtk.TreeStore(str, object)
        self.tree.set_model(self.model)
        select_path = (0,)

        # sets up the default panes
        for page in self.PAGES:
            self.model.append(None, [page.name, page])

        self.plug_root = self.model.append(None, [_('Plugins'),
            plugin_prefs])

        self._load_plugin_pages()

        selection = self.tree.get_selection()
        selection.connect('changed', self.switch_pane)
        # Disallow selection on rows with no widget to show
        # (e.g. the "Plugins" parent node).
        selection.set_select_function(lambda path:
            self.model[path][1] is not None)

        gobject.idle_add(selection.select_path, select_path)

    def _load_plugin_pages(self):
        self._clear_children(self.plug_root)
        plugin_pages = []
        plugin_manager = self.main.exaile.plugins
        
        for plugin in self.plugins:
            name = plugin
            if plugin in plugin_manager.enabled_plugins:
                plugin = plugin_manager.enabled_plugins[plugin]
                if hasattr(plugin, 'get_prefs_pane'):
                    try:
                        plugin_pages.append(plugin.get_prefs_pane())
                    except:
                        logger.warning('Error loading preferences pane')
                        traceback.print_exc()

        import locale
        plugin_pages.sort(key=lambda x: locale.strxfrm(x.name))

        for page in plugin_pages:
            self.model.append(self.plug_root, [page.name, page])

        gobject.idle_add(self.tree.expand_row,
            self.model.get_path(self.plug_root), False)

    def _clear_children(self, node):
        remove = []
        iter = self.model.iter_children(node)
        while iter:
            remove.append(iter)
            iter = self.model.iter_next(iter)

        for iter in remove:
            self.model.remove(iter)

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.builder.connect_signals({
            'on_cancel_button_clicked': lambda *e: self.cancel(),
            'on_apply_button_clicked': self.apply,
            'on_ok_button_clicked': self.ok,
        })

    def ok(self, widget):
        """
            Called when the user clicks 'ok'
        """
        if self.apply(None): 
            self.cancel()
            self.window.hide()
            self.window.destroy()
            if hasattr(self.last_page, 'page_leave'):
                self.last_page.page_leave(self)

    def apply(self, widget):
        """
            Applies settings
        """
        for page in self.fields.values():
            for field in page:
                if not field.apply():
                    return False

        for k, v in self.panes.iteritems():
            if hasattr(k, 'apply'):
                k.apply(self)

        self.settings.copy_settings(_SETTINGSMANAGER)

        return True

    def cancel(self):
        """
            Closes the preferences dialog, ensuring that the osd popup isn't
            still showing
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
        if not iter: return
        page = self.model.get_value(iter, 1)
        if not page: return

        if self.last_child:
            self.box.remove(self.last_child)

        if self.last_page:
            if hasattr(self.last_page, 'page_leave'): 
                self.last_page.page_leave(self)

        self.last_page = page

        child = self.panes.get(page)
        if not child:
            if hasattr(page, 'ui'):
                import gtk
                builder = gtk.Builder()
                builder.add_from_file(page.ui)
            else:
                try:
                    logger.warning('Please switch to gtk.Builder for preferences panes')
                    import gtk.glade
                    builder = gtk.glade.XML(page.glade, 'prefs_pane')
                    builder.get_object = builder.get_widget
                    builder.connect_signals = builder.signal_autoconnect
                except ImportError:
                    logger.error('Importing Glade as fallback failed')
                    return

            child = builder.get_object('prefs_pane')
            init = getattr(page, 'init', None)
            if init: init(self, builder)
            self.panes[page] = child
            self.builders[page] = builder

        if not page in self.fields:
            self._populate_fields(page, self.builders[page])

        if hasattr(page, 'page_enter'):
            page.page_enter(self)

        child.unparent()
        self.box.pack_start(child, True, True)
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
                if inspect.isclass(klass) and \
                    issubclass(klass, widgets.PrefsItem): 
                    widget = builder.get_object(klass.name)
                    if not widget:
                        logger.warning('Invalid prefs widget: %s' % klass.name) 
                        continue
                    field = klass(self, widget)
                    self.fields[page].append(field)
            except:
                logger.warning('Broken prefs class: %s' % attr)
                traceback.print_exc()
 
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
