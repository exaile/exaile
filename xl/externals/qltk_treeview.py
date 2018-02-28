
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

import contextlib

# Taken from QuodLibet: quodlibet/qltk/__init__.py
#
# Copyright 2005 Joe Wreschnig, Michael Urman
#           2012 Christoph Reiter
#          2016-17 Nick Boultbee
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

def get_primary_accel_mod():
    """Returns the primary Gdk.ModifierType modifier.

    cmd on osx, ctrl everywhere else.
    """

    return Gtk.accelerator_parse("<Primary>")[1]


def is_accel(event, *accels):
    """Checks if the given keypress Gdk.Event matches
    any of accelerator strings.

    example: is_accel(event, "<shift><ctrl>z")

    Args:
        *accels: one ore more `str`
    Returns:
        bool
    Raises:
        ValueError: in case any of the accels could not be parsed
    """

    assert accels

    if event.type != Gdk.EventType.KEY_PRESS:
        return False

    # ctrl+shift+x gives us ctrl+shift+X and accelerator_parse returns
    # lowercase values for matching, so lowercase it if possible
    keyval = event.keyval
    if not keyval & ~0xFF:
        keyval = ord(chr(keyval).lower())

    default_mod = Gtk.accelerator_get_default_mod_mask()
    keymap = Gdk.Keymap.get_default()

    for accel in accels:
        accel_keyval, accel_mod = Gtk.accelerator_parse(accel)
        if accel_keyval == 0 and accel_mod == 0:
            raise ValueError("Invalid accel: %s" % accel)

        # If the accel contains non default modifiers matching will
        # never work and since no one should use them, complain
        non_default = accel_mod & ~default_mod
        if non_default:
            print("Accelerator '%s' contains a non default modifier '%s'." %
                (accel, Gtk.accelerator_name(0, non_default) or ""))

        # event.state contains the real mod mask + the virtual one, while
        # we usually pass only virtual one as text. This adds the real one
        # so they match in the end.
        accel_mod = keymap.map_virtual_modifiers(accel_mod)[1]

        # Remove everything except default modifiers and compare
        if (accel_keyval, accel_mod) == (keyval, event.state & default_mod):
            return True

    return False


def is_instance_of_gtype_name(instance, name):
    """Returns False if the gtype can't be found"""

    try:
        gtype = GObject.type_from_name(name)
    except Exception:
        return False
    else:
        pytype = gtype.pytype
        if pytype is None:
            return False
        return isinstance(instance, pytype)

def is_wayland():
    display = Gdk.Display.get_default()
    if display is None:
        return False
    return is_instance_of_gtype_name(display, "GdkWaylandDisplay")

def menu_popup(menu, shell, item, func, *args):
    """Wrapper to fix API break:
    https://git.gnome.org/browse/gtk+/commit/?id=8463d0ee62b4b22fa
    """

    if func is not None:
        def wrap_pos_func(menu, *args):
            return func(menu, args[-1])
    else:
        wrap_pos_func = None

    return menu.popup(shell, item, wrap_pos_func, *args)

# Taken from QuodLibet: quodlibet/qltk/views.py
#
# Copyright 2005 Joe Wreschnig, Michael Urman
#           2012, 2013 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


class DragScroll(object):
    """A treeview mixin for smooth drag and scroll (needs BaseView).

    Call scroll_motion in the 'drag-motion' handler and
    scroll_disable in the 'drag-leave' handler.

    """

    __scroll_delay = None
    __scroll_periodic = None
    __scroll_args = (0, 0, 0, 0)
    __scroll_length = 0
    __scroll_last = None

    def __enable_scroll(self):
        """Start scrolling if it hasn't already"""
        if self.__scroll_periodic is not None or \
                self.__scroll_delay is not None:
            return

        def periodic_scroll():
            """Get the tree coords for 0,0 and scroll from there"""
            wx, wy, dist, ref = self.__scroll_args
            x, y = self.convert_widget_to_tree_coords(0, 0)
            x, y = self.convert_bin_window_to_widget_coords(x, y)

            # We reached an end, stop
            if self.__scroll_last == y:
                self.scroll_disable()
                return
            self.__scroll_last = y

            # If we went full speed for a while.. speed up
            # .. every number is made up here
            if self.__scroll_length >= 50 * ref:
                dist *= self.__scroll_length / (ref * 10)
            if self.__scroll_length < 2000 * ref:
                self.__scroll_length += abs(dist)

            try:
                self.scroll_to_point(-1, y + dist)
            except OverflowError:
                pass
            self.set_drag_dest(wx, wy)
            # we have to re-add the timeout.. otherwise they could add up
            # because scroll can last longer than 50ms
            GLib.source_remove(self.__scroll_periodic)
            self.__scroll_periodic = None
            enable_periodic_scroll()

        def enable_periodic_scroll():
            self.__scroll_periodic = GLib.timeout_add(50, periodic_scroll)
            self.__scroll_delay = None

        self.__scroll_delay = GLib.timeout_add(350, enable_periodic_scroll)

    def scroll_disable(self):
        """Disable all scrolling"""
        if self.__scroll_periodic is not None:
            GLib.source_remove(self.__scroll_periodic)
            self.__scroll_periodic = None
        if self.__scroll_delay is not None:
            GLib.source_remove(self.__scroll_delay)
            self.__scroll_delay = None
        self.__scroll_length = 0
        self.__scroll_last = None

    def scroll_motion(self, x, y):
        """Call with current widget coords during a dnd action to update
           scrolling speed"""

        visible_rect = self.get_visible_rect()
        if visible_rect is None:
            self.scroll_disable()
            return

        # I guess the bin to visible_rect difference is the header height
        # but this could be wrong
        start = self.convert_bin_window_to_widget_coords(0, 0)[1]
        end = visible_rect.height + start

        # Get the font height as size reference
        reference = max(self.create_pango_layout("").get_pixel_size()[1], 1)

        # If the drag is in the scroll area, adjust the speed
        scroll_offset = int(reference * 3)
        in_upper_scroll = (start < y < start + scroll_offset)
        in_lower_scroll = (y > end - scroll_offset)

        # thanks TI200
        def accel(x):
            try:
                return int(1.1 ** (x * 12 / reference)) - (x / reference)
            except ValueError:
                return 0

        if in_lower_scroll:
            diff = accel(y - end + scroll_offset)
        elif in_upper_scroll:
            diff = - accel(start + scroll_offset - y)
        else:
            self.scroll_disable()
            return

        # The area where we can go to full speed
        full_offset = int(reference * 0.8)
        in_upper_full = (start < y < start + full_offset)
        in_lower_full = (y > end - full_offset)
        if not in_upper_full and not in_lower_full:
            self.__scroll_length = 0

        # For the periodic scroll function
        self.__scroll_args = (x, y, diff, reference)

        # The area to trigger a scroll is a bit smaller
        trigger_offset = int(reference * 2.5)
        in_upper_trigger = (start < y < start + trigger_offset)
        in_lower_trigger = (y > end - trigger_offset)

        if in_upper_trigger or in_lower_trigger:
            self.__enable_scroll()


class BaseView(Gtk.TreeView):

    __gsignals__ = {
        # like the tree selection changed signal but doesn't emit twice in case
        # a row is activated
        'selection-changed': (
            GObject.SignalFlags.RUN_LAST, None, (object, )),
    }

    def __init__(self, *args, **kwargs):
        super(BaseView, self).__init__(*args, **kwargs)
        self.connect("key-press-event", self.__key_pressed)
        self._setup_selection_signal()

    def _setup_selection_signal(self):
        # Forwards selection changed events except in case row-activated
        # just happened and the selection changed event is a result of the
        # button release after the row-activated event.
        # This makes the selection change only once in case of double clicking
        # a row.

        self._sel_ignore_next = False
        self._sel_ignore_time = -1

        def on_selection_changed(selection):
            if self._sel_ignore_time != Gtk.get_current_event_time():
                self.emit("selection-changed", selection)
            self._sel_ignore_time = -1

        id_ = self.get_selection().connect('changed', on_selection_changed)

        def on_destroy(self):
            self.get_selection().disconnect(id_)

        self.connect('destroy', on_destroy)

        def on_row_activated(*args):
            self._sel_ignore_next = True

        self.connect_after("row-activated", on_row_activated)

        def on_button_release_event(self, event):
            if self._sel_ignore_next:
                self._sel_ignore_time = Gtk.get_current_event_time()
            self._sel_ignore_next = False

        self.connect("button-release-event", on_button_release_event)

    def do_key_press_event(self, event):
       if is_accel(event, "space", "KP_Space"):
           return False
       return Gtk.TreeView.do_key_press_event(self, event)

    def __key_pressed(self, view, event):
    
        def get_first_selected():
            selection = self.get_selection()
            model, paths = selection.get_selected_rows()
            return paths and paths[0] or None
    
        if is_accel(event, "Right") or is_accel(event, "<Primary>Right"):
            first = get_first_selected()
            if first:
                self.expand_row(first, False)
        elif is_accel(event, "Left") or is_accel(event, "<Primary>Left"):
            first = get_first_selected()
            if first:
                if self.row_expanded(first):
                    self.collapse_row(first)
                else:
                    # if we can't collapse, move the selection to the parent,
                    # so that a second attempt collapses the parent
                    model = self.get_model()
                    parent = model.iter_parent(model.get_iter(first))
                    if parent:
                        self.set_cursor(model.get_path(parent))

    def remove_paths(self, paths):
        """Remove rows and restore the selection if it got removed"""

        model = self.get_model()
        self.remove_iters([model.get_iter(p) for p in paths])

    def remove_iters(self, iters):
        """Remove rows and restore the selection if it got removed"""

        self.__remove_iters(iters)

    def remove_selection(self):
        """Remove all currently selected rows and select the position
        of the first removed one."""

        selection = self.get_selection()
        mode = selection.get_mode()
        if mode in (Gtk.SelectionMode.SINGLE, Gtk.SelectionMode.BROWSE):
            model, iter_ = selection.get_selected()
            if iter_:
                self.__remove_iters([iter_], force_restore=True)
        elif mode == Gtk.SelectionMode.MULTIPLE:
            model, paths = selection.get_selected_rows()
            iters = list(map(model.get_iter, paths or []))
            self.__remove_iters(iters, force_restore=True)

    def select_by_func(self, func, scroll=True, one=False):
        """Calls func with every Gtk.TreeModelRow in the model and selects
        it if func returns True. In case func never returned True,
        the selection will not be changed.

        Returns True if the selection was changed."""

        model = self.get_model()
        if not model:
            return False

        selection = self.get_selection()
        first = True
        for row in model:
            if func(row):
                if not first:
                    selection.select_path(row.path)
                    continue
                self.set_cursor(row.path)
                if scroll:
                    self.scroll_to_cell(row.path, use_align=True,
                                        row_align=0.5)
                first = False
                if one:
                    break
        return not first

    def iter_select_by_func(self, func, scroll=True):
        """Selects the next row after the current selection for which func
        returns True, removing the selection of all other rows.

        func gets passed Gtk.TreeModelRow and should return True if
        the row should be selected.

        If scroll=True then scroll to the selected row if the selection
        changes.

        Returns True if the selection was changed.
        """

        model = self.get_model()
        if not model:
            return False

        if not model.get_iter_first():
            # empty model
            return False

        selection = self.get_selection()
        model, paths = selection.get_selected_rows()

        # get the last iter we shouldn't be looking at
        if not paths:
            last_iter = model[-1].iter
        else:
            last_iter = model.get_iter(paths[-1])

        # get the first iter we should be looking at
        start_iter = model.iter_next(last_iter)
        if start_iter is None:
            start_iter = model.get_iter_first()

        row_iter = Gtk.TreeModelRowIter(model, start_iter)

        for row in row_iter:
            if not func(row):
                continue
            self.set_cursor(row.path)
            if scroll:
                self.scroll_to_cell(row.path, use_align=True,
                                    row_align=0.5)
            return True

        last_path = model.get_path(last_iter)
        for row in model:
            if row.path.compare(last_path) == 0:
                return False
            if not func(row):
                continue
            self.set_cursor(row.path)
            if scroll:
                self.scroll_to_cell(row.path, use_align=True,
                                    row_align=0.5)
            return True

        return False

    def set_drag_dest(self, x, y, into_only=False):
        """Sets a drag destination for widget coords

        into_only will only highlight rows or the whole widget and no
        lines between rows.
        """

        dest_row = self.get_dest_row_at_pos(x, y)
        if dest_row is None:
            rows = len(self.get_model())
            if not rows:
                (self.get_parent() or self).drag_highlight()
            else:
                self.set_drag_dest_row(Gtk.TreePath(rows - 1),
                                       Gtk.TreeViewDropPosition.AFTER)
        else:
            path, pos = dest_row
            if into_only:
                if pos == Gtk.TreeViewDropPosition.BEFORE:
                    pos = Gtk.TreeViewDropPosition.INTO_OR_BEFORE
                elif pos == Gtk.TreeViewDropPosition.AFTER:
                    pos = Gtk.TreeViewDropPosition.INTO_OR_AFTER
            self.set_drag_dest_row(path, pos)

    def __remove_iters(self, iters, force_restore=False):
        if not iters:
            return

        selection = self.get_selection()
        model = self.get_model()

        if force_restore:
            for iter_ in iters:
                model.remove(iter_)
        else:
            old_count = selection.count_selected_rows()
            for iter_ in iters:
                model.remove(iter_)
            # only restore a selection if all selected rows are gone afterwards
            if not old_count or selection.count_selected_rows():
                return

        # model.remove makes the removed iter point to the next row if possible
        # so check if the last iter is a valid one and select it or
        # simply select the last row
        if model.iter_is_valid(iters[-1]):
            selection.select_iter(iters[-1])
        elif len(model):
            selection.select_path(model[-1].path)

    @contextlib.contextmanager
    def without_model(self):
        """Conext manager which removes the model from the view
        and adds it back afterwards.

        Tries to preserve all state that gets reset on a model change.
        """

        old_model = self.get_model()
        search_column = self.get_search_column()
        sorts = [column.get_sort_indicator() for column in self.get_columns()]
        self.set_model(None)

        yield old_model

        self.set_model(old_model)
        self.set_search_column(search_column)
        for column, value in zip(self.get_columns(), sorts):
            column.set_sort_indicator(value)


class MultiDragTreeView(BaseView):
    """TreeView with multirow drag support.

    Button press events which would result in a row getting unselected
    get delayed until the next button release event.

    This makes it possible to drag one or more selected rows without
    changing the selection.
    """

    def __init__(self, *args, **kwargs):
        super(MultiDragTreeView, self).__init__(*args, **kwargs)
        self.connect('button-press-event', self.__button_press)
        self.connect('button-release-event', self.__button_release)
        self.__pending_action = None

    def __button_press(self, view, event):
        if event.button == Gdk.BUTTON_PRIMARY:
            return self.__block_selection(event)

    def __block_selection(self, event):
        x, y = map(int, [event.x, event.y])
        try:
            path, col, cellx, celly = self.get_path_at_pos(x, y)
        except TypeError:
            return True
        selection = self.get_selection()
        is_selected = selection.path_is_selected(path)
        mod_active = event.get_state() & (
            get_primary_accel_mod() | Gdk.ModifierType.SHIFT_MASK)

        if is_selected:
            self.__pending_action = (path, col, mod_active)
            selection.set_select_function(lambda *args: False, None)
        else:
            self.__pending_action = None
            selection.set_select_function(lambda *args: True, None)

    def __button_release(self, view, event):
        if self.__pending_action:
            path, col, single_unselect = self.__pending_action
            selection = self.get_selection()
            selection.set_select_function(lambda *args: True, None)
            if single_unselect:
                selection.unselect_path(path)
            else:
                self.set_cursor(path, col, 0)
            self.__pending_action = None


class RCMTreeView(BaseView):
    """Emits popup-menu when a row is right-clicked on."""

    def __init__(self, *args, **kwargs):
        super(RCMTreeView, self).__init__(*args, **kwargs)
        self.connect('button-press-event', self.__button_press)

    def __button_press(self, view, event):
        if event.button == Gdk.BUTTON_SECONDARY:
            return self.__check_popup(event)

    def __check_popup(self, event):
        x, y = map(int, [event.x, event.y])
        try:
            path, col, cellx, celly = self.get_path_at_pos(x, y)
        except TypeError:
            return True
        self.grab_focus()
        selection = self.get_selection()
        if not selection.path_is_selected(path):
            self.set_cursor(path, col, 0)
        else:
            col.focus_cell(col.get_cells()[0])
        self.__position_at_mouse = True
        self.emit('popup-menu')
        return True

    def ensure_popup_selection(self):
        try:
            self.__position_at_mouse
        except AttributeError:
            path, col = self.get_cursor()
            if path is None:
                return False
            self.scroll_to_cell(path, col)
            # ensure current cursor path is selected, just like right-click
            selection = self.get_selection()
            if not selection.path_is_selected(path):
                selection.unselect_all()
                selection.select_path(path)
            return True

    def popup_menu(self, menu, button, time):
        try:
            del self.__position_at_mouse
        except AttributeError:
            # suppress menu if the cursor isn't on a real path
            if not self.ensure_popup_selection():
                return False
            pos_func = self.__popup_position
        else:
            pos_func = None

        # force attach the menu to the view
        attached_widget = menu.get_attach_widget()
        if attached_widget != self:
            if attached_widget is not None:
                menu.detach()
            menu.attach_to_widget(self, None)

        menu_popup(menu, None, None, pos_func, None, button, time)
        return True

    def __popup_position(self, menu, *args):
        path, col = self.get_cursor()

        # get a rectangle describing the cell render area (assume 3 px pad)
        rect = self.get_cell_area(path, col)
        padding = 3
        rect.x += padding
        rect.width = max(rect.width - padding * 2, 0)
        rect.y += padding
        rect.height = max(rect.height - padding * 2, 0)

        x, y = self.get_window().get_origin()[1:]
        x, y = self.convert_bin_window_to_widget_coords(x + rect.x, y + rect.y)

        menu.realize()
        ma = menu.get_allocation()
        menu_y = rect.height + y
        if self.get_direction() == Gtk.TextDirection.LTR:
            menu_x = x
        else:
            menu_x = x - ma.width + rect.width

        # on X11/win32 we can use the screen size
        if not is_wayland():

            # fit menu to screen, aligned per text direction
            screen = self.get_screen()
            screen_width = screen.get_width()
            screen_height = screen.get_height()

            # show above row if no space below and enough above
            if menu_y + ma.height > screen_height and y - ma.height > 0:
                menu_y = y - ma.height

            # make sure it's not outside of the screen
            if self.get_direction() == Gtk.TextDirection.LTR:
                menu_x = max(0, min(menu_x, screen_width - ma.width))
            else:
                menu_x = min(max(0, menu_x), screen_width)

        return (menu_x, menu_y, True)  # x, y, move_within_screen


class AllTreeView(RCMTreeView, MultiDragTreeView, DragScroll):
    """A combined TreeView"""
    pass
