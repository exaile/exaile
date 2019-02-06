# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import threading

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

import xl.trax
import xlgui.guiutil
import xlgui.panel

from xl.common import threaded

from _base import PLUGIN_INFO, SETTINGS, Logger, get_path
from _database import ConnectionStatus, FileChooserDialog, get_connection_status
from _pattern import parse_patterns
from _search import mount_where_sql
from _tree_view import CollectionTreeView
from _utils import ADDITIONAL_FILTER_NONE_VALUE
from _widgets import Widgets


#: Logger
_LOGGER = Logger(__name__)


class MainPanel(xlgui.panel.Panel):
    """
        Main panel
    """
    def __init__(self, exaile):
        """
            Constructor
            :param exaile: Exaile
        """
        super(MainPanel, self).__init__(
            exaile.gui.main.window, PLUGIN_INFO.id, PLUGIN_INFO.name
        )
        self.append_items = exaile.gui.main.on_append_items
        self.additional_filter = ADDITIONAL_FILTER_NONE_VALUE
        self.model = None
        self.word = ''
        self.last_keyboard_event = None

        self.__setup_widgets([
            {'panel_stack':
                (
                    {'msg_box': (
                        {'info_stack': ('initial_box', {'error_box': 'path_label'})},
                        'open_database_button'
                    ), },
                    {'collection_box': ['combo_box', 'refresh_button', 'search_entry', 'tree']}
                )
            },
            'combo_box_model'
        ])

        SETTINGS.EVENT.connect(self.on_setting_changed)
        self.__check_connection_status()

        # Simulates a change for first load
        SETTINGS.EVENT.log(None, 'patterns')

    @property
    def menu(self):
        """
            Retrieves menu from tree
            :return: _menu.Menu
        """
        return self.tree.menu

    @property
    def current_view_pattern(self):
        """
            The current view pattern
            :return: _view_pattern.ViewPattern
        """
        return self.view_patterns[self.widgets["combo_box"].get_active()]

    @property
    def ui_info(self):
        """
            A way to dynamically get path
            :return: (str - path, str - main panel)
            :see: super.ui_info var
        """
        return get_path('panel.ui'), 'panel_stack'

    def __check_connection_status(self):
        """
            Check the connection status loading the correct view
            :return: True if connection status is fine
        """
        widgets = self.widgets
        connection_status = get_connection_status()
        is_error = (connection_status == ConnectionStatus.Error)
        widgets["error_box" if is_error else "initial_box"].visible()
        if is_error:
            widgets["path_label"].set_text(SETTINGS["database"])

        is_fine = (connection_status == ConnectionStatus.Fine)
        widgets["collection_box" if is_fine else "msg_box"].visible()

        return is_fine

    def __repopulate_pattern_combo_box(self):
        """
            Repopulate pattern views
            :return: None
        """
        widgets = self.widgets
        with self.widgets["combo_box"].events['changed'].suspended:
            widgets["combo_box_model"].clear()
            for i in self.view_patterns:
                widgets["combo_box_model"].append([i.name])

        widgets["combo_box"].set_active_id(SETTINGS['current_view_pattern'])
        if widgets["combo_box"].get_active() == -1:
            widgets["combo_box"].set_active(0)

    def __setup_widgets(self, ws):
        """
            Setup widgets
            :return: None
        """
        self.tree = CollectionTreeView(self)
        self.widgets = Widgets(
            self.builder, ws,
            combo_box=self.on_pattern_combo_box_changed,
            open_database_button=lambda *_: FileChooserDialog(self.parent).run(),
            refresh_button=self.on_refresh_button_activate,
            search_entry=self.on_search_entry_activate,
        )
        self.widgets["tree"] = self.tree

        self.filter = xlgui.guiutil.SearchEntry(self.widgets["search_entry"])

        collection_box = self.widgets["collection_box"]
        self.tree_box = tree_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        tree_box.pack_start(scroll, True, True, 0)

        collection_box.pack_start(tree_box, True, True, 0)
        collection_box.show_all()

    def drag_get_data(self, treeview, _context, selection, _target_id, _etime):
        """
            Called when a drag source wants data for this drag operation
        """
        selection.set_uris(
            xl.trax.util.get_uris_from_tracks(
                treeview.get_selected_tracks()
            )
        )

    def on_search_entry_activate(self, entry):
        """
            Searches tracks and reloads the tree
            :param entry: Gtk.Entry
            :return: None
        """
        value = entry.get_text()
        self.additional_filter = mount_where_sql(
            value, self.current_view_pattern.all_fields
        ) if value else ADDITIONAL_FILTER_NONE_VALUE

        self.tree.load()

    def on_pattern_combo_box_changed(self, _combo_box):
        """
            Treat changes on pattern combo box
            :param _combo_box: Gtk.ComboBox
            :return: None
        """
        if get_connection_status() == ConnectionStatus.Fine:
            self.tree.load()

        active_id = self.widgets["combo_box"].get_active_id()
        SETTINGS['current_view_pattern'] = active_id if active_id else ''

    def on_refresh_button_activate(self, button):
        """
            Called on activation of refresh button
            :param button: Gtk.Button
            :return: None
        """

        def set_sensitive(status):
            """
                Set button sensitive
                :param status: bool
                :return: None
            """
            button.set_sensitive(status)
            button.grab_focus()

        @threaded
        def wait_end(end_event):
            """
                Wait it ends and reset button sensitivity
                :param end_event: threading.Event
                :return: None
            """
            end_event.wait()
            GLib.idle_add(lambda: set_sensitive(True))

        set_sensitive(False)
        notify_end = threading.Event()
        wait_end(notify_end)
        self.tree.load(None, notify_end=notify_end)

    def on_setting_changed(self, _event_name, _obj, key):
        """
            On setting changed
            :param _event_name: str
            :param _obj: SETTINGS
            :param key: simplest setting name
            :return: None
        """
        if key == 'database':
            if self.__check_connection_status():
                self.tree.load()
        elif key in ('patterns', 'icons', 'icon_size'):
            view_patterns = parse_patterns(SETTINGS['patterns'])
            if len(view_patterns) == 0:
                _LOGGER.info("using default view patterns")
                view_patterns = parse_patterns(SETTINGS.DEFAULTS['patterns']())

            self.view_patterns = view_patterns
            self.__repopulate_pattern_combo_box()
        elif key == 'draw_separators':
            if get_connection_status() == ConnectionStatus.Fine:
                self.tree.load()
        elif key == 'font':
            font = SETTINGS['font']
            if font:
                self.tree.text_cell.set_property('font-desc',
                                            Pango.FontDescription.from_string(font))
                self.tree.columns_autosize()

