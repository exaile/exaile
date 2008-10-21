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

import thread, os, shlex, string, urllib2
from xl.nls import gettext as _
import pygtk
pygtk.require('2.0')
import gtk, gtk.glade
from xl import xdg
from xlgui.prefs.widgets import *
from xlgui.prefs import general_prefs, osd_prefs
import logging

logger = logging.getLogger(__name__)

class PreferencesDialog(object):
    """
        Preferences Dialog
    """

    PAGES = (general_prefs,)# osd_prefs)

    def __init__(self, parent, main, plugin_page=None):
        """
            Initilizes the preferences dialog
        """
        self.main = main
        self.last_child = None
        self.parent = parent
        self.settings = self.main.exaile.settings
        self.plugins = self.main.exaile.plugins.enabled_plugins
        self.fields = {} 
        self.panes = {}
        self.xmls = {}
        self.popup = None
        self.xml = gtk.glade.XML(xdg.get_data_path('glade/preferences_dialog.glade'), 
            'PreferencesDialog', 'exaile')
        xml = self.xml
        self.window = self.xml.get_widget('PreferencesDialog')
        self.window.set_transient_for(parent)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.window.connect('delete-event', lambda *e: self.cancel())

        self._connect_events()

        self.label = self.xml.get_widget('prefs_frame_label')
        self.box = self.xml.get_widget('prefs_box')

        self.tree = self.xml.get_widget('prefs_tree')
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Preferences'), text, text=0)
        self.tree.append_column(col)

        self.model = gtk.TreeStore(str, object)
        self.tree.set_model(self.model)
        count = 0
        select_path = (0,)

        # sets up the default panes
        for page in self.PAGES:
            self.model.append(None, [page.name, page])

        plugin_pages = []
        for k, plugin in self.plugins.iteritems():
            if hasattr(plugin, 'get_prefs_pane'):
                if k == plugin_page:
                    select_path = count
                plugin_pages.append(plugin.get_prefs_pane())
                count += 1

        if plugin_pages:
            plug_root = self.model.append(None, [_('Plugins'), None])
            for page in plugin_pages:
                self.model.append(plug_root, [page.name, page])

        if not type(select_path) == tuple:
            self.tree.expand_row(self.model.get_path(plug_root), False)
            select_path = (1, select_path)

        selection = self.tree.get_selection()
        selection.connect('changed', self.switch_pane)
        selection.select_path(select_path)

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.xml.signal_autoconnect({
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

    def apply(self, widget):
        """
            Applies settings
        """
        for page in self.fields.values():
            for field in page:
                if not field.apply():
                    print field.name
                    return False

        return True

    def cancel(self):
        """
            Closes the preferences dialog, ensuring that the osd popup isn't
            still showing
        """
        self.window.hide()
        self.window.destroy()

    def switch_pane(self, selection):
        """
            Switches a pane
        """
        (model, iter) = selection.get_selected()
        if not iter: return
        page = self.model.get_value(iter, 1)
        if not page: return
        self.label.set_markup("<b>%s</b>" %
            page.name)

        if self.last_child:
            self.box.remove(self.last_child)

        if not page in self.panes:
            xml = gtk.glade.XML(page.glade, 'prefs_window')
            window = xml.get_widget('prefs_window')
            child = xml.get_widget('prefs_pane')
            window.remove(child)
            self.panes[page] = child
            self.xmls[page] = xml
        else:
            child = self.panes[page]

        if not page in self.fields:
            self._populate_fields(page, self.xmls[page])
                
        self.box.pack_start(child, True, True)
        self.last_child = child
        self.box.show_all()

    def _populate_fields(self, page, xml):
        """
            Populates field pages
        """
        self.fields[page] = []

        attributes = dir(page)
        for attr in attributes:
            try:
                if not 'Preference' in attr: continue
                klass = getattr(page, attr)
                if not type(klass) == type: continue

                widget = xml.get_widget(klass.name)
                if not widget:
                    logger.warning('Invalid prefs widget: %s' % klass.name) 
                    continue
                field = klass(self, widget)
                self.fields[page].append(field)
            except:
                logger.warning('Broken prefs class: %s' % attr)
 
    def run(self):
        """
            Runs the dialog
        """
        self.window.show_all()

class BlankClass(object):
    pass
