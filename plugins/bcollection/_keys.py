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
from sys import maxint as MAX_INT
import threading

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from xl.common import threaded

import _keys
import _model

from _base import SETTINGS, Logger
from _utils import normalize

#: Logger
_LOGGER = Logger(__name__)

#: tuple: Key values to ignore
IGNORED_KEY_VALS = (
    Gdk.KEY_Alt_L,
    Gdk.KEY_Alt_R,
    Gdk.KEY_Control_L,
    Gdk.KEY_Control_R,
    Gdk.KEY_Delete,
    Gdk.KEY_Insert,
    Gdk.KEY_Down,
    Gdk.KEY_Up,
    Gdk.KEY_Home,
    Gdk.KEY_End,
    Gdk.KEY_Meta_L,
    Gdk.KEY_Meta_R,
    Gdk.KEY_Prior,
    Gdk.KEY_Next,
    Gdk.KEY_Shift_L,
    Gdk.KEY_Shift_R,
    Gdk.KEY_VoidSymbol,
    Gdk.KEY_BackSpace,
)


def key_pressed_is_a_word(tree, evt):
    """
        Check if the key pressed compounds a word
        :param tree: Gtk.TreeView
        :param evt: Gdk.EventKey
        :return: bool
    """
    keyval_unicode = Gdk.keyval_to_unicode(evt.keyval)
    keyval_normalized = normalize(unichr(keyval_unicode)) if keyval_unicode else None
    if keyval_normalized:
        if evt.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.LOCK_MASK):
            search_entry = tree.container.widgets['search_entry']
            search_entry.grab_focus()
            search_entry.set_text(keyval_normalized.upper())
            search_entry.select_region(-1, -1)
            return True

    current_view_pattern = tree.container.current_view_pattern
    model = tree.model

    first_path, focus_column = tree.get_cursor()
    first_it = model.get_iter(first_path)
    first_it_string = model.get_string_from_iter(first_it)

    def treat_word(word):
        """
            From current cursor position, try to find something that starts with the 'word'
            (search includes all output fields, sequentially, as defined on pattern)
            :param word: str
            :return: bool
        """

        def check_word(it, path):
            """
                Check a word for a path
                :param it: Gtk.TreeIter
                :param path: Gtk.TreePath
                :return: bool
            """
            value = _model.get_value_array(model, it)
            depth = model.iter_depth(it)

            if value:
                for i in current_view_pattern[depth].outputs['tree_view'].fields:
                    try:
                        s = unicode(value[current_view_pattern[depth].fields.index(i)])
                    except ValueError:
                        continue
                    else:
                        if normalize(s).startswith(word):
                            tree.set_cursor(path, None, False)
                            tree.scroll_to_cell(path, None, True, 0.2, 0)
                            return True

            return False

        def check_children(it, path):
            """
                Check for all children
                :param it: Gtk.TreeIter
                :param path: Gtk.TreePath
                :return: bool
            """
            if tree.row_expanded(path):
                it = model.iter_children(it)
                while it and not check(it, model.get_path(it)):
                    it = model.iter_next(it)

                return it is not None
            else:
                return False

        def check(it, path):
            """
                High level word check and children
                :param it: Gtk.TreeIter
                :param path: Gtk.TreePath
                :return: bool
            """
            if not check_word(it, path):
                if model.get_string_from_iter(it) == first_it_string:
                    raise StopIteration()

                return check_children(it, path)
            else:
                return True

        treated = False
        it = first_it
        if len(word) > 1:
            # Treats first current/initial path
            treated = check_word(first_it, first_path)

        if not treated:
            treated = check_children(first_it, first_path)

        while not treated:
            it_next = model.iter_next(it)
            while it_next is None:
                it_parent = model.iter_parent(it)
                if it_parent:
                    it = it_parent
                    it_next = model.iter_next(it_parent)
                else:
                    it_next = model.get_iter_first()
                    break  # it_parent should never be None here (fallback)

            it = it_next
            path = model.get_path(it)
            try:
                treated = check(it, path)
            except StopIteration:
                return False

        return treated

    treated = False
    if not (evt.state & Gtk.accelerator_get_default_mod_mask()):
        from datetime import timedelta, datetime

        old_keyboard_event = tree.last_keyboard_event
        current_datetime = datetime.utcnow()

        if (
            old_keyboard_event is None
            or (old_keyboard_event + timedelta(seconds=2)) <= current_datetime
        ):
            tree.word = ''

        keyval_unicode = Gdk.keyval_to_unicode(evt.keyval)
        if keyval_unicode:
            keyval_char = unichr(keyval_unicode)
            word = tree.word + keyval_char

            try:
                treated = treat_word(word)
            except StopIteration:
                pass

            if not treated and len(word) > 1:
                word = unicode(keyval_char)
                try:
                    treated = treat_word(word)
                except StopIteration:
                    pass

            if treated:
                tree.word = word
                tree.last_keyboard_event = current_datetime

    return treated


def key_pressed_to_change_font_size(tree, evt):
    """
        Check if key pressed is to change font size (Ctrl +/-)
        :param tree: Gtk.TreeView
        :param evt: Gdk.EventKey
        :return: bool
    """
    font_size_factor = 0
    if evt.state & Gtk.accelerator_get_default_mod_mask():
        if evt.keyval == Gdk.KEY_KP_Add:
            font_size_factor = 1
        elif evt.keyval == Gdk.KEY_KP_Subtract:
            font_size_factor = -1

    if font_size_factor != 0:
        font_desc = tree.text_cell.get_property('font-desc').copy()
        size = font_desc.get_size()
        size += (2 * Pango.SCALE) * font_size_factor
        if size >= 0:
            font_desc.set_size(size)
            SETTINGS['font'] = font_desc.to_string()

        return True

    return False


def key_pressed_to_surf_in_tree(tree, evt):
    """
        Check if key pressed surf on tree, selects, move cursor...
        :param tree: Gtk.TreeView
        :param evt: Gdk.EventKey
        :return: bool
    """
    current_view_pattern = tree.container.current_view_pattern

    @threaded
    def expand_rows(paths_):
        """
            Load rows on a thread (one by one)
            :param paths_: [Gtk.TreeRowReference]
            :return: None
        """
        notify_end = threading.Event()
        for i in paths_:
            notify_end.clear()

            tree.EXPAND_ROW_EVENT.log(tree, (i, current_view_pattern, notify_end))

            # Wait it ends
            notify_end.wait()

    # Declare
    selection = tree.get_selection()
    (model, paths) = selection.get_selected_rows()

    def is_all_expanded():
        """
            Check if all subsequent paths (children) are expanded
            :return: bool
        """

        def is_expanded(it):
            """
                Check if an iterator and children are expanded
                :param it: Gtk.TreeIter
                :return: bool
            """
            if not model.iter_has_child(it):
                return True

            row_expanded = tree.row_expanded(model.get_path(it))
            if row_expanded:
                for i in _model.get_each_child(model, it):
                    if not is_expanded(i):
                        return False

            return row_expanded

        for path in paths:
            if not is_expanded(model.get_iter(path)):
                return False

        return True

    if evt.keyval in (Gdk.KEY_asterisk, Gdk.KEY_KP_Multiply):
        if not is_all_expanded():
            tree.expand_rows(
                [Gtk.TreeRowReference.new(model, path) for path in paths], [-MAX_INT]
            )
        else:
            for path in paths:
                initial_iter = model.get_iter(path)
                if model.iter_has_child(initial_iter):
                    selection.unselect_iter(initial_iter)
                    for i in _model.get_child(model, initial_iter):
                        selection.select_iter(i)

        return True
    elif evt.keyval in (Gdk.KEY_slash, Gdk.KEY_KP_Divide):
        is_on_top = True
        rows = []
        for path in paths:
            last_iter_parent = initial_iter = model.get_iter(path)
            it = model.iter_parent(initial_iter)
            while it:
                last_iter_parent = it
                is_on_top = False
                it = model.iter_parent(it)

            rows.append((initial_iter, last_iter_parent))

        if is_on_top:
            for path in paths:
                tree.collapse_row(path)
        else:
            # First put selection on top
            for (initial_iter, last_iter_parent) in rows:
                selection.unselect_iter(initial_iter)
                selection.select_iter(last_iter_parent)

        return True

    rows_reference = []
    select_range_from_parent = []

    # Ignore expansions
    with tree.events['row-expanded'].suspended:
        if evt.keyval == Gdk.KEY_space:
            for path in paths:
                it = model.get_iter(path)
                if model.iter_has_child(it):
                    if not tree.collapse_row(path):
                        tree.expand_row(path, False)
                        rows_reference.append(Gtk.TreeRowReference.new(model, path))

        elif evt.keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Subtract, Gdk.KEY_minus):
            for path in paths:
                if not tree.collapse_row(path):
                    it_parent = model.iter_parent(model.get_iter(path))
                    if it_parent is not None:
                        selection.unselect_path(path)
                        selection.select_path(model.get_path(it_parent))

        elif evt.keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Add, Gdk.KEY_plus):
            for path in paths:
                it = model.get_iter(path)
                if model.iter_has_child(it):
                    if not tree.expand_row(path, False):
                        selection.unselect_path(path)
                        select_range_from_parent.append(it)

                    rows_reference.append(Gtk.TreeRowReference.new(model, path))
                else:
                    it_parent = model.iter_parent(it)
                    if it_parent:
                        select_range_from_parent.append(it_parent)
        else:
            return False

        for i in set(select_range_from_parent):
            n = 0
            it = model.iter_nth_child(i, n)
            while it:
                selection.select_iter(it)
                n += 1
                it = model.iter_nth_child(i, n)

        if rows_reference:
            expand_rows(rows_reference)

        return True


def key_pressed_is_menu_or_return(tree, evt):
    """
        Check if key pressed is to show menu, or to append items
        :param tree: Gtk.TreeView
        :param evt: Gdk.EventKey
        :return: bool
    """
    if evt.keyval == Gdk.KEY_Menu:
        Gtk.Menu.popup(tree.menu, None, None, None, None, 0, evt.time)
        return True
    elif evt.keyval in (Gdk.KEY_Return, Gdk.KEY_space):
        tree.container.append_items(tree.get_selected_tracks(), force_play=True)
        return True

    return False


def key_pressed_is_tab(tree, evt):
    """
        Check if key pressed is a tab key
        :param tree: Gtk.TreeView
        :param evt: Gdk.EventKey
        :return: bool
    """
    is_tab = evt.keyval == Gdk.KEY_Tab
    if is_tab:
        tree.container.widgets[
            'search_entry' if (evt.state & Gdk.ModifierType.SHIFT_MASK) else 'combo_box'
        ].grab_focus()

    return is_tab


def on_key_press_event(tree, evt):
    """
        Called when a key is pressed in the tree
        :param tree: Gtk.TreeView
        :param evt: Gdk.EventKey
        :return: bool
        :see: Gtk.Widget.signals.key_press_event
    """
    treated = False
    if evt.keyval not in IGNORED_KEY_VALS:
        for x in [
            _keys.key_pressed_is_tab,
            _keys.key_pressed_is_menu_or_return,
            _keys.key_pressed_to_change_font_size,
            _keys.key_pressed_to_surf_in_tree,
            _keys.key_pressed_is_a_word,
        ]:
            treated = x(tree, evt)
            if treated:
                break

    # Post action
    if not treated:
        tree.word = ''
        tree.last_keyboard_event = None

    _LOGGER.debug('on_key_pressed %s, %s, %s', treated, evt.keyval, tree.word)
    return treated
