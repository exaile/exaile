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

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

import xl
import xlgui

import _keys
import _loader
import _model
import _monitor
import _widgets

from _base import PLUGIN_INFO, SETTINGS, Logger, create_event
from _database import execute_select
from _menu import Menu
from _utils import create_stacked_images_pixbuf, get_error_icon

#: Logger
_LOGGER = Logger(__name__)


class CollectionTreeView(xlgui.widgets.common.DragTreeView):
    """
        The tree view
    """

    #: Event: Event to request expansion
    EXPAND_ROW_EVENT = create_event('expand-row')

    def __init__(self, container):
        """
            Constructor
            :param container: Container
        """
        super(CollectionTreeView, self).__init__(container, receive=False, source=True)

        self.model = None

        self.set_has_tooltip(True)

        self.set_headers_visible(False)

        self.set_property('margin-bottom', 10)
        self.set_property('enable-search', False)

        self.set_row_separator_func(_model.row_separator_func, None)

        self.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self.__setup_column()

        self.__connect_events()

        self.menu = Menu(container)

        self.last_keyboard_event = None

        self.word = ''

    def __connect_events(self):
        """
            Connect events
            :return: None
        """
        self.EXPAND_ROW_EVENT.connect(self.on_expand_row, self)

        _widgets.connect(self, ['row-expanded'], self.on_row_expanded)
        _widgets.connect(self, ['query-tooltip'], self.on_query_tooltip)
        _widgets.connect(self, ['key-press-event'], _keys.on_key_press_event)

    def get_tracks_uri_for_path(self, path):
        """
            Get tracks uri for a path from model
            :param path: Gtk.TreePath
            :return: yield str
        """
        model = self.get_model()
        view_pattern = self.container.current_view_pattern
        additional_filter = self.container.additional_filter
        it = model.get_iter(path)
        if _model.get_value_array(model, it):
            depth = model.iter_depth(it)
            subgroup = view_pattern[depth]
            parent_values = _model.get_parent_values(model, it)
            select_params = (
                subgroup.get_select_path(parent_values, additional_filter[0]),
                (filter(lambda x: x is not None, parent_values) + additional_filter[1]),
            )
            for row in execute_select(*select_params):
                if xl.trax.is_valid_track(unicode(row[0])):
                    yield row[0]

    def yield_selected_tracks_uri(self):
        """
            Yield the currently selected tracks
            :return: yield str
        """
        model, paths = self.get_selection().get_selected_rows()
        for path in paths:
            for uri in self.get_tracks_uri_for_path(path):
                yield uri

    def yield_selected_tracks(self, scan=False):
        """
            Yield the currently selected tracks
            :return: yield tracks (xl.trax.Track)
        """
        model, paths = self.get_selection().get_selected_rows()
        for path in paths:
            for track in self.get_tracks_for_path(path, scan):
                yield track

    def get_tracks_for_path(self, path, scan=False):
        """
            Get tracks for a path from model (expand item)
            :param path: Gtk.TreePath
            :return: yield tracks (xl.trax.Track)
        """
        for i in self.get_tracks_uri_for_path(path):
            location = unicode(i)
            if xl.trax.is_valid_track(location):
                yield xl.trax.Track(uri=location, scan=scan)

    def get_selected_tracks(self, scan=False):
        """
            Returns the currently selected tracks
        """
        return list(self.yield_selected_tracks(scan))

    def get_selected_tracks_uri(self):
        """
            Returns the currently selected tracks
        """
        return list(self.yield_selected_tracks_uri())

    # Overrides super
    def on_drag_begin(self, _widget, context):
        """
            Use icons to represent items,
            putting it as a *stacked image*

            Overrides super
            :see: Gtk.Widget.signals.drag_begin
        """
        # Parent operations
        self.drag_context = context
        Gdk.drag_abort(context, Gtk.get_current_event_time())

        self.reset_selection_status()

        # Setup icon
        model, paths = self.get_selection().get_selected_rows()
        icon_size = Gtk.icon_size_lookup(Gtk.IconSize.DND)[1]
        icons = []
        view_pattern = self.container.current_view_pattern
        for path in paths:
            it = model.get_iter(path)
            icons.append(
                view_pattern[model.iter_depth(it)].icons['tree_view']
                if _model.get_value_array(model, it)
                else get_error_icon(icon_size)
            )

            if len(icons) >= 8:
                break

        Gtk.drag_set_icon_pixbuf(
            context, create_stacked_images_pixbuf(icons, icon_size, 0.25, 180), 0, 0
        )

    def on_expand_row(self, _evt_name, _tree, data):
        """
            Handles self.__ExpandRowEvent
            :param _evt_name: str
            :param _tree: Gtk.TreeView
            :param data: (row_ref, view_pattern, end_notify)
            :return: None
        """
        treated = False
        row_ref, view_pattern, end_notify = data
        if row_ref.valid():
            model = row_ref.get_model()
            if model is self.model:
                _loader.load(
                    model,
                    view_pattern,
                    model.get_iter(row_ref.get_path()),
                    end_notify,
                    self.container.additional_filter,
                )
                treated = True

        if not treated:
            end_notify.set()

    def on_row_expanded(self, _tree, it, _path):
        """
            Called when a user expands a tree item

            Loads the various nodes that belong under this (it)
            :param _tree: Gtk.TreeView
            :param it: Gtk.TreeIter
            :param _path: Gtk.TreePath
            :return: None
        """
        self.load(it)

    @staticmethod
    def on_query_tooltip(widget, x, y, keyboard_mode, tooltip):
        """
            Set up the tooltip
            :param widget: Gtk.Widget
            :param x: int
            :param y: int
            :param keyboard_mode: bool
            :param tooltip: Gtk.Tooltip
            :return: bool
        """
        if not widget.get_tooltip_context(x, y, keyboard_mode):
            return False

        result = widget.get_path_at_pos(x, y)
        if not result:
            return False

        path = result[0]
        model = widget.get_model()
        it = model.get_iter(path)
        val = model.get_value(it, _model.index("TooltipText"))
        if val:
            font = SETTINGS['font']
            tooltip.set_markup(
                val if not font else ('<span font="%s">%s</span>' % (font, val))
            )
            icon = model.get_value(it, _model.index("TooltipIcon"))
            if icon:
                tooltip.set_icon(icon)

            widget.set_tooltip_row(tooltip, path)
            return True
        else:
            return False

    def __setup_column(self):
        """
            Set up column to tree
            :return: None
        """
        column = Gtk.TreeViewColumn()

        pixbuf_cell = Gtk.CellRendererPixbuf()

        column.pack_start(pixbuf_cell, False)
        column.set_attributes(pixbuf_cell, pixbuf=_model.index("Icon"))

        text_cell = self.text_cell = Gtk.CellRendererText()

        if xl.settings.get_option('gui/ellipsize_text_in_panels', False):
            text_cell.set_property('ellipsize-set', True)
            text_cell.set_property('ellipsize', Pango.EllipsizeMode.END)

        font = SETTINGS['font']
        if font:
            text_cell.set_property('font-desc', Pango.FontDescription.from_string(font))

        column.pack_start(text_cell, True)
        column.set_attributes(text_cell, markup=_model.index("Title"))

        self.append_column(column)

    # Overrides super
    def on_button_press(self, widget, event):
        """
            Overrides super treating button press event
            :param widget: Gtk.Widget
            :param event: Gdk.EventButton
            :return: bool
            :see: Gtk.Widget.signals.button_press_event
        """
        if super(self.__class__, self).on_button_press(widget, event):
            return True
        elif event.type == getattr(Gdk.EventType, '2BUTTON_PRESS'):
            self.container.append_items(
                self.get_selected_tracks(),
                replace=xl.settings.get_option('playlist/replace_content', False),
            )
        elif event.button == Gdk.BUTTON_MIDDLE:
            target = self.get_target_for(event)
            if target:
                if not target.is_selected:
                    self.set_cursor(target.path, target.column, False)
                    self.container.append_items(
                        self.get_selected_tracks(), replace=True
                    )
                return True
        elif event.triggers_context_menu():
            target = self.get_target_for(event)
            if target:
                model = self.model
                if not _model.get_value_array(model, model.get_iter(target.path)):
                    # Ignore
                    del self.pending_events[:]

        return False

    @xl.common.threaded
    def expand_rows(self, row_refs, total_rows):
        """
            Load rows on a thread (one by one)
            :param row_refs: list of Gtk.TreeRowReference
            :return: None
        """
        notify_end = threading.Event()
        for row_ref in row_refs:
            notify_end.clear()

            self.EXPAND_ROW_EVENT.log(
                self, (row_ref, self.container.current_view_pattern, notify_end)
            )
            # Wait it ends
            notify_end.wait()

        GLib.idle_add(self.check_and_expand, row_refs, total_rows)

    def check_and_expand(self, row_references, total_rows):
        """
            If the row still valid, and has not reached
            the maximum auto expanding rows setting,
            expand it
            :param row_references: list of Gtk.TreeRowReference
            :param total_rows: [int] total of expanded rows
            :return: None
        """
        max_expand = SETTINGS['expand']
        row_references_ = []
        for row_reference in row_references:
            model = row_reference.get_model()

            if not row_reference.valid() or model is not self.model:
                return

            path = row_reference.get_path()
            it = model.get_iter(path)

            total_it = model.iter_n_children(it)
            if total_it > 0 and total_rows[0] + total_it <= max_expand:
                total_rows[0] += total_it
                self.expand_to_path(path)
                row_references_.append(row_reference)

        if total_rows[0] <= max_expand and row_references_:
            rows = []
            for row_reference in row_references_:
                model = row_reference.get_model()
                path = row_reference.get_path()
                it = model.get_iter(path)

                it_children = model.iter_children(it)
                while it_children is not None:
                    children_path = model.get_path(it_children)
                    rows.append(Gtk.TreeRowReference.new(model, children_path))
                    it_children = model.iter_next(it_children)

            self.expand_rows(rows, total_rows)

    def load(self, parent=None, notify_end=None):
        """
            Loads item
            :param parent:
            :param notify_end:
            :return:
        """

        @xl.common.threaded
        def expand(model, notify_end):
            """
                Wait the end to request next
                :param model: Gtk.TreeModel
                :param notify_end: threading.Event or None
                :return: None
            """
            notify_end.wait()

            def consume_rows():
                """
                    Sequentially consume the rows to expand it (before reaching total_rows)
                    :return: None
                """
                if model is self.model:
                    rows = []
                    it = model.get_iter_first()
                    while it is not None:
                        value = _model.get_value_array(model, it)
                        if value:
                            path = model.get_path(it)
                            rows.append(Gtk.TreeRowReference.new(model, path))

                        it = model.iter_next(it)

                    total_rows = [len(rows)]
                    if 0 < total_rows[0] <= SETTINGS['expand']:
                        self.expand_rows(rows, total_rows)

            GLib.idle_add(consume_rows)

        model = self.model
        if parent is None:
            _monitor.update_last_load()

            model = self.model = _model.new()
            self.set_model(model)
            if SETTINGS['expand'] > 0:
                if notify_end is None:
                    notify_end = threading.Event()

                expand(model, notify_end)

        _loader.load(
            model,
            self.container.current_view_pattern,
            parent,
            notify_end,
            self.container.additional_filter,
        )
