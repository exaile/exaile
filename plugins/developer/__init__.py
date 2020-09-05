# Copyright (C) 2017 Dustin Spicuzza
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


from gi.repository import GLib
from gi.repository import Gtk

from xl import event, providers
from xl.nls import gettext as _

from xlgui.guiutil import GtkTemplate
from xlgui.widgets import menu

import threading


class DeveloperPlugin:
    """
    Shows useful information for Exaile developers
    """

    def enable(self, exaile):
        self.lock = threading.RLock()

        self.exaile = exaile
        self.window = None
        self.menu = None

        # Event data storage
        self.events = {'__all': 0}
        self.capture_events = True

        # subscribe for all events
        event.add_callback(self.on_events)

    def disable(self, exaile):
        self.teardown(exaile)

    def teardown(self, exaile):
        event.remove_callback(self.on_events)
        if self.window:
            self.window.destroy()
        if self.menu:
            providers.unregister('menubar-tools-menu', self.menu)

    def on_gui_loaded(self):

        # add a thing to the view menu
        self.menu = menu.simple_menu_item(
            'developer', '', _('Developer Tools'), callback=self.on_view_menu
        )

        providers.register('menubar-tools-menu', self.menu)

    def on_view_menu(self, widget, name, parent, context):
        if self.window:
            self.window.present()
        else:
            self.window = DeveloperWindow(self.exaile.gui.main.window, self)

            def _delete(w, e):
                self.window = None

            self.window.connect('delete-event', _delete)
            self.window.show_all()

    #
    # Capture callback stuff
    #

    def clear_events(self):
        with self.lock:
            self.events.clear()
            self.events['__all'] = 0

    def pause_events(self, pause):
        with self.lock:
            self.capture_events = pause

    def on_events(self, etype, *args):
        with self.lock:
            if not self.capture_events:
                return
            self.events['__all'] += 1
            try:
                self.events[etype] += 1
            except KeyError:
                self.events[etype] = 1

    def get_event_data(self, last_count):
        with self.lock:
            all_count = self.events['__all']
            if all_count != last_count:
                return self.events.copy(), all_count


plugin_class = DeveloperPlugin


@GtkTemplate('developer_window.ui', relto=__file__)
class DeveloperWindow(Gtk.Window):

    __gtype_name__ = 'DeveloperWindow'

    (
        event_filter_entry,
        event_model_filter,
        event_tree,
        event_store,
    ) = GtkTemplate.Child.widgets(4)

    def __init__(self, parent, plugin):
        Gtk.Window.__init__(self)
        self.init_template()

        if parent:
            self.set_transient_for(parent)

        self.events_count = None
        self.plugin = plugin
        self.event_filter_text = ''

        # key: name, value: iter
        self.event_model_idx = {}

        self.event_model_filter.set_visible_func(self.on_event_filter_row)

        self.event_tree.set_search_entry(self.event_filter_entry)
        self.event_tree.connect(
            'start-interactive-search', lambda *a: self.event_filter_entry.grab_focus()
        )

        self.event_timeout_id = GLib.timeout_add(250, self.on_event_update)

    @GtkTemplate.Callback
    def on_clear_events(self, widget):
        self.plugin.clear_events()
        self.events_count = None
        self.event_model_idx.clear()
        self.event_store.clear()

    @GtkTemplate.Callback
    def on_delete(self, widget, event):
        GLib.source_remove(self.event_timeout_id)

    def on_event_filter_row(self, model, titer, unused):
        row = model.get(titer, 0)
        if row:
            return self.event_filter_text in row[0]

    @GtkTemplate.Callback
    def on_event_pause_toggle(self, widget):
        self.plugin.pause_events(widget.get_active())

    @GtkTemplate.Callback
    def on_event_filter_entry_changed(self, widget):
        self.event_filter_text = widget.get_text()
        self.event_model_filter.refilter()

    def on_event_update(self):
        '''Periodically updates the displayed list of events'''
        data = self.plugin.get_event_data(self.events_count)
        if data:
            events, self.events_count = data
            for name, count in events.items():
                titer = self.event_model_idx.get(name)
                if titer:
                    self.event_store[titer][1] = count
                else:
                    titer = self.event_store.append([name, count])
                    self.event_model_idx[name] = titer

        return True
