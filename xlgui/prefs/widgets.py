# Copyright (C) 2008-2009 Adam Olsen 
#
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

import gtk.gdk, hashlib, os, pango
from xl.nls import gettext as _

class PrefsItem(object):
    """
        Representing a gtk.Entry preferences item
    """
    default = ''
    def __init__(self, prefs, widget):
        """
            Initializes the preferences item
            expects the name of the widget in the .glade file, the default for
            this setting, an optional function to be called when the value is
            changed, and an optional function to be called when this setting
            is applied
        """

        self.widget = widget
        self.prefs = prefs

        self._set_value()
        self._setup_change()

    def change(self, *args):
        self.apply()

    def _setup_change(self):
        """
            Sets up the function to be called when this preference is changed
        """
        self.widget.connect('focus-out-event',
            self.change, self.name, self._get_value())

        try:
            self.widget.connect('activate',
                lambda *e: self.change(self.widget, None, self.name,
                    self._get_value()))
        except TypeError:
            pass

    def _set_value(self):
        """ 
            Sets the GUI widget up for this preference
        """
        if not self.widget:
            xlmisc.log("Widget not found: %s" % (self.name))
            return
        self.widget.set_text(str(self.prefs.settings.get_option(
            self.name, self.default)))

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        return unicode(self.widget.get_text(), 'utf-8')

    def apply(self, value=None):
        """
            Applies this setting
        """
        if hasattr(self, 'done') and not self.done(): return False
        if value is None:
            value = self._get_value()
        self.prefs.settings.set_option(self.name, value)
        return True

class HashedPrefsItem(PrefsItem):
    """
        Represents a text entry with automated hashing
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)
        self._dirty = False

    def _setup_change(self):
        self.widget.connect('changed', self.change)

    def change(self, *e):
        self._dirty = True
        self.apply()

    def apply(self, value=None):
        """
            Applies this setting
        """
        if hasattr(self, 'done') and not self.done(): return False
        if value is None:
            value = self._get_value()
        if value is None:
            return True

        if self._dirty:
            try:
                hashfunc = getattr(hashlib, self.type)
                value = hashfunc(value).hexdigest()
                self._dirty = False
            except AttributeError:
                value = ''

        self.prefs.settings.set_option(self.name, value)
        return True

class CheckPrefsItem(PrefsItem):
    """
        A class to represent check boxes in the preferences window
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('toggled',
            self.change)

    def _set_value(self):
        self.widget.set_active(
            self.prefs.settings.get_option(self.name,
            self.default))

    def _get_value(self):
        return self.widget.get_active()


class DirPrefsItem(PrefsItem):
    """
        Directory chooser button
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        pass

    def _set_value(self):
        """
            Sets the current directory
        """
        directory = os.path.expanduser(
            self.prefs.settings.get_option(self.name, self.default))
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.widget.set_filename(directory)

    def _get_value(self):
        return self.widget.get_filename()


class OrderListPrefsItem(PrefsItem):
    """ 
        A list box with reorderable items
    """
    def __init__(self, prefs, widget):
        self.model = gtk.ListStore(str)
        self.items = []
        PrefsItem.__init__(self, prefs, widget)
        widget.set_headers_visible(False)
        widget.set_reorderable(True)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Item", text, text=0)
        self.widget.append_column(col)
        self.widget.set_model(self.model)

    def _setup_change(self):
        self.widget.connect('drag-end', self.change)

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        items = self.prefs.settings.get_option(self.name,
            self.default)

        self.model.clear()
        for item in items:
            self.model.append([item])

    def _get_value(self):
        items = []
        iter = self.model.get_iter_first()
        while iter:
            items.append(self.model.get_value(iter, 0))
            iter = self.model.iter_next(iter)
        self.items = items
        return items


class SelectionListPrefsItem(PrefsItem):
    """
        Two list boxes allowing to drag items
        to each other, reorderable

        Options:
        * available_title (Title of the list of available items)
        * selected_title (Title of the list of selected items)
        * available_items (Dictionary of items and their titles)
        * fixed_items (Dictionary of non-removable items and their titles)
    """
    def __init__(self, prefs, widget):
        self.available_list = gtk.ListStore(str)
        self.selected_list = gtk.ListStore(str)
        self._update_lists(self.default)

        # Make sure container is empty
        for child in widget.get_children():
            widget.remove(child)

        PrefsItem.__init__(self, prefs, widget)
        widget.set_homogeneous(False)
        widget.set_spacing(6)

        text = gtk.CellRendererText()
        available_tree = gtk.TreeView(self.available_list)
        available_tree.set_reorderable(True)
        self.available_selection = available_tree.get_selection()
        available_col = gtk.TreeViewColumn(None, text, text=0)
        try:
            available_col.set_title(self.available_title)
        except AttributeError:
            pass
        available_tree.append_column(available_col)

        selected_tree = gtk.TreeView(self.selected_list)
        selected_tree.set_reorderable(True)
        self.selected_selection = selected_tree.get_selection()
        selected_col = gtk.TreeViewColumn(None, text, text=0)
        try:
            selected_col.set_title(self.selected_title)
        except AttributeError:
            pass
        selected_tree.append_column(selected_col)

        add_button = gtk.Button()
        add_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_BUTTON))
        add_button.set_tooltip_text(_('Add item'))
        add_button.set_sensitive(False)
        remove_button = gtk.Button()
        remove_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_BACK, gtk.ICON_SIZE_BUTTON))
        remove_button.set_tooltip_text(_('Remove item'))
        remove_button.set_sensitive(False)

        control_box = gtk.VBox(spacing=3)
        control_box.pack_start(add_button, expand=False)
        control_box.pack_start(remove_button, expand=False)
        control_panel = gtk.Alignment(xalign=0.5, yalign=0.5,
            xscale=0.0, yscale=0.0)
        control_panel.add(control_box)

        up_button = gtk.Button()
        up_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_UP, gtk.ICON_SIZE_BUTTON))
        up_button.set_tooltip_text(_('Move selected item up'))
        up_button.set_sensitive(False)
        down_button = gtk.Button()
        down_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_DOWN, gtk.ICON_SIZE_BUTTON))
        down_button.set_tooltip_text(_('Move selected item down'))
        down_button.set_sensitive(False)

        move_box = gtk.VBox(spacing=3)
        move_box.pack_start(up_button, expand=False)
        move_box.pack_start(down_button, expand=False)
        move_panel = gtk.Alignment(xalign=0.5, yalign=0.5, xscale=0.0, yscale=0.0)
        move_panel.add(move_box)

        widget.pack_start(available_tree)
        widget.pack_start(control_panel, expand=False)
        widget.pack_start(selected_tree)
        widget.pack_start(move_panel, expand=False)

        add_button.connect('clicked', self.on_add_button_clicked)
        remove_button.connect('clicked', self.on_remove_button_clicked)
        up_button.connect('clicked', self.on_up_button_clicked)
        down_button.connect('clicked', self.on_down_button_clicked)

        self.available_selection.connect('changed',
            self.on_available_selection_changed,
            [add_button])
        self.selected_selection.connect('changed',
            self.on_selected_selection_changed,
            [remove_button, up_button, down_button])

        # Allow to send rows to selected
        available_tree.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK,
            [('TREE_MODEL_ROW', gtk.TARGET_SAME_APP, 0)],
            gtk.gdk.ACTION_MOVE)
        # Allow to receive rows from selected
        available_tree.enable_model_drag_dest(
            [('TREE_MODEL_ROW', gtk.TARGET_SAME_APP, 0)],
            gtk.gdk.ACTION_MOVE)
        # Allow to send rows to available
        selected_tree.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK,
            [('TREE_MODEL_ROW', gtk.TARGET_SAME_APP, 0)],
            gtk.gdk.ACTION_MOVE)
        # Allow to receive rows from available
        selected_tree.enable_model_drag_dest(
            [('TREE_MODEL_ROW', gtk.TARGET_SAME_APP, 0)],
            gtk.gdk.ACTION_MOVE)

        available_tree.connect('drag-data-received', self.on_drag_data_received)
        available_tree.connect('key-press-event', self.on_available_tree_key_pressed)
        selected_tree.connect('drag-data-received', self.on_drag_data_received)
        selected_tree.connect('key-press-event', self.on_selected_tree_key_pressed)

        self.available_list.connect('row-inserted',
            self.on_available_list_row_inserted, available_tree)
        self.selected_list.connect('row-inserted',
            self.on_selected_list_row_inserted, selected_tree)

    def on_available_selection_changed(self, selection, buttons):
        """
            Enables buttons if there is at least one row selected
        """
        row_selected = (selection.count_selected_rows() > 0)

        for button in buttons:
            button.set_sensitive(row_selected)

    def on_selected_selection_changed(self, selection, buttons):
        """
            Enables buttons if there is at least one row selected
        """
        row_selected = (selection.count_selected_rows() > 0)

        for button in buttons:
            button.set_sensitive(row_selected)

    def on_add_button_clicked(self, button):
        """
            Moves the selected rows to
            the list of selected items
        """
        available_list, paths = self.available_selection.get_selected_rows()
        iter = available_list.get_iter(paths[0])
        value = available_list.get_value(iter, 0)

        available_list.remove(iter)
        iter = None

        self.selected_list.append([value])

    def on_remove_button_clicked(self, button):
        """
            Moves the selected rows to
            the list of available items
        """
        selected_list, paths = self.selected_selection.get_selected_rows()
        iter = selected_list.get_iter(paths[0])
        value = selected_list.get_value(iter, 0)

        selected_list.remove(iter)
        iter = None

        self.available_list.append([value])

    def on_up_button_clicked(self, button):
        """
            Moves the selected rows upwards
        """
        list, paths = self.selected_selection.get_selected_rows()
        iter = list.get_iter(paths[0])
        upper_iter = self.iter_prev(iter, list)

        if upper_iter is None:
            return

        list.swap(upper_iter, iter)

    def on_down_button_clicked(self, button):
        """
            Moves the selected rows downwards
        """
        list, paths = self.selected_selection.get_selected_rows()
        iter = list.get_iter(paths[0])
        lower_iter = list.iter_next(iter)

        if lower_iter is None:
            return

        list.swap(iter, lower_iter)

    def on_available_tree_key_pressed(self, tree, event):
        """
        """
        if not event.state & gtk.gdk.MOD1_MASK: return

        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname == 'Right':
            self.on_add_button_clicked(None)

    def on_selected_tree_key_pressed(self, tree, event):
        """
        """
        if not event.state & gtk.gdk.MOD1_MASK: return

        keyname = gtk.gdk.keyval_name(event.keyval)
        
        if keyname == 'Left':
            self.on_remove_button_clicked(None)
        elif keyname == 'Up':
            self.on_up_button_clicked(None)
        elif keyname == 'Down':
            self.on_down_button_clicked(None)

    def on_drag_data_received(self, target_treeview, context, x, y, data, info, time):
        """
            Handles movement of rows
        """
        source_treeview = context.get_source_widget()
        source_list, paths = source_treeview.get_selection().get_selected_rows()
        source_iter = source_list.get_iter(paths[0])
        source_value = source_list.get_value(source_iter, 0)

        if source_value in self.fixed_items.values():
            return

        source_list.remove(source_iter)
        source_iter = None

        target_list = target_treeview.get_model()
        target_row = target_treeview.get_dest_row_at_pos(x, y)
        if target_row is None:
            target_list.append([source_value])
        else:
            target_path, drop_position = target_row
            target_iter = target_list.get_iter(target_path)
            if drop_position == gtk.TREE_VIEW_DROP_BEFORE or \
                drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
                target_list.insert_before(target_iter, [source_value])
            else:
                target_list.insert_after(target_iter, [source_value])
            target_iter = None

    def on_available_list_row_inserted(self, list, path, iter, tree):
        """
            Selects moved rows and focuses tree
        """
        self.available_selection.select_path(path)
        tree.grab_focus()

    def on_selected_list_row_inserted(self, list, path, iter, tree):
        """
            Selects moved rows and focuses tree
        """
        self.selected_selection.select_path(path)
        tree.grab_focus()

    def iter_prev(self, iter, model):
        """
            Returns the previous iter
            Taken from PyGtk FAQ 13.51
        """
        path = model.get_path(iter)
        position = path[-1]

        if position == 0:
            return None

        prev_path = list(path)[:-1]
        prev_path.append(position - 1)
        prev = model.get_iter(tuple(prev_path))

        return prev

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        items = self.prefs.settings.get_option(self.name, self.default)
        self._update_lists(items)

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        items = []
        iter = self.selected_list.get_iter_first()
        while iter:
            selected_value = self.selected_list.get_value(iter, 0)
            for id, title in self.available_items.iteritems():
                if selected_value == title:
                    items.append(id)
                    break
            iter = self.selected_list.iter_next(iter)
        return items

    def _update_lists(self, items):
        """
            Updates the two lists
        """
        available_set = set(self.available_items.keys())
        available_set = available_set.difference(set(items))

        self.available_list.clear()

        for id in available_set:
            self.available_list.append([self.available_items[id]])

        self.selected_list.clear()

        for id in items:
            try:
                self.selected_list.append([self.available_items[id]])
            except KeyError:
              pass
        try:
            for id, title in self.fixed_items.iteritems():
                self.selected_list.append([title])
        except AttributeError:
            pass


class ShortcutListPrefsItem(PrefsItem):
    """
        A list showing available items and allowing
        to assign/edit/remove key accelerators
    """
    def __init__(self, prefs, widget):
        self.list = gtk.ListStore(str, str)

        PrefsItem.__init__(self, prefs, widget)

        self.widget.set_model(self.list)

        title_renderer = gtk.CellRendererText()
        title_column = gtk.TreeViewColumn(_('Action'), title_renderer, text=0)
        title_column.set_expand(True)
        title_column.set_cell_data_func(title_renderer, self.title_data_func)
        accel_renderer = gtk.CellRendererAccel()
        accel_renderer.set_property('editable', True)
        accel_renderer.set_property('style', pango.STYLE_OBLIQUE)
        accel_renderer.connect('accel-cleared', self.on_accel_cleared)
        accel_renderer.connect('accel-edited', self.on_accel_edited)
        accel_column = gtk.TreeViewColumn(_('Shortcut'), accel_renderer, text=1)
        accel_column.set_expand(True)

        self.widget.append_column(title_column)
        self.widget.append_column(accel_column)

    def title_data_func(self, celllayout, cell, model, iter):
        """
            Renders human readable titles instead of the actual keys
        """
        key = model.get_value(iter, 0)

        try:
            cell.set_property('text', self.available_items[key])
        except:
            pass

    def on_accel_cleared(self, cellrenderer, path):
        """
            Clears accelerators in the list
        """
        iter = self.list.get_iter(path)
        self.list.set_value(iter, 1, '')

    def on_accel_edited(self, cellrenderer, path, accel_key, accel_mods, keycode):
        """
            Updates accelerators display in the list
        """
        accel = gtk.accelerator_name(accel_key, accel_mods)
        iter = self.list.get_iter(path)
        self.list.set_value(iter, 1, accel)

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        items = self.prefs.settings.get_option(self.name, self.default)
        self.update_list(items)

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        option = {}

        iter = self.list.get_iter_first()
        while iter:
            action = self.list.get_value(iter, 0)
            accel = self.list.get_value(iter, 1)
            if accel:
                option[action] = accel
            iter = self.list.iter_next(iter)
        
        return option

    def update_list(self, items):
        """
            Updates the displayed items
        """
        self.list.clear()
        for action in self.available_items.iterkeys():
            try:
                accel = items[action]
            except KeyError:
                accel = ''
            self.list.append([action, accel])


class TextViewPrefsItem(PrefsItem):
    """
        Represents a gtk.TextView
    """
    def __init__(self, prefs, widget):
        """
            Initializes the object
        """
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('focus-out-event', self.change)

    def get_all_text(self):
        """
            Returns the value of the text buffer
        """
        buf = self.widget.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return unicode(buf.get_text(start, end), 'utf-8')

    def _set_value(self):
        """
            Sets the value of this widget
        """
        self.widget.get_buffer().set_text(str(
            self.prefs.settings.get_option(self.name,
            default=self.default)))

    def _get_value(self):    
        """
            Applies the setting
        """
        return self.get_all_text()


class ListPrefsItem(PrefsItem):
    """
        A class to represent a space separated list in the preferences window
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _set_value(self):
        items = self.prefs.settings.get_option(self.name, 
            default=self.default)
        try:
            items = " ".join(items)
        except:
            items = ""
        self.widget.set_text(items)

    def _get_value(self):
        # shlex is broken with unicode, so we feed it UTF-8 and decode
        # afterwards.
        values = shlex.split(self.widget.get_text())
        values = [unicode(value, 'utf-8') for value in values]
        return values


class SpinPrefsItem(PrefsItem):
    """
        A class to represent a numeric entry box with stepping buttons
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _set_value(self):
        value = self.prefs.settings.get_option(self.name, 
            default=self.default)
        self.widget.set_value(value)

    def _setup_change(self):
        self.widget.connect('value-changed', self.change)

    def _get_value(self):
        return self.widget.get_value()

class ScalePrefsItem(SpinPrefsItem):
    """
        Representation of gtk.Scale widgets
    """
    def __init__(self, prefs, widget):
        SpinPrefsItem.__init__(self, prefs, widget)

class FloatPrefsItem(PrefsItem):
    """
        A class to represent a floating point number in the preferences window
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _set_value(self):
        self.widget.set_text(str(
            self.prefs.settings.get_option(self.name, 
            default=self.default)))

    def _get_value(self):
        return float(self.widget.get_text())


class IntPrefsItem(FloatPrefsItem):

    def _get_value(self):
        return int(self.widget.get_text())


class ColorButtonPrefsItem(PrefsItem):
    """
        A class to represent the color button in the prefs window
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('color-set', self.change)

    def _set_value(self):
        self.widget.set_color(gtk.gdk.color_parse(
            self.prefs.settings.get_option(self.name, 
            self.default)))

    def _get_value(self):
        color = self.widget.get_color()
        string = "#%.2x%.2x%.2x" % (color.red / 257, color.green / 257, 
            color.blue / 257)
        return string


class FontButtonPrefsItem(ColorButtonPrefsItem):
    """
        Font button
    """
    def __init__(self, prefs, widget):
        ColorButtonPrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('font-set', self.change)

    def _set_value(self):
        font = self.prefs.settings.get_option(self.name, 
            self.default)
        self.widget.set_font_name(font)
        
    def _get_value(self):
        font = self.widget.get_font_name()
        return font


class ComboPrefsItem(PrefsItem):
    """
        A combo box
    """
    def __init__(self, prefs, widget, use_index=False, use_map=False):
        self.use_index = use_index
        self.use_map = use_map
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('changed', self.change)

    def _set_value(self):
        item = self.prefs.settings.get_option(self.name, 
            self.default)

        if self.use_map:
            index = self.map.index(self.prefs.settings.get_option(
                        self.name, self.default))
            self.widget.set_active(index)
            return

        if self.use_index:
            index = self.prefs.settings.get_option(self.name, 
                self.default)
            self.widget.set_active(index)
            return

        model = self.widget.get_model()
        iter = model.get_iter_first()
        count = 0
        while True:
            value = model.get_value(iter, 0)
            if value == item:
                self.widget.set_active(count)
                break
            count += 1
            iter = model.iter_next(iter)
            if not iter: break

    def _get_value(self):
        if self.use_map:
            return self.map[self.widget.get_active()]
        elif self.use_index:
            return self.widget.get_active()
        else:
            return self.widget.get_active_text()


class ComboEntryPrefsItem(PrefsItem):
    """
        A combo box allowing for user defined
        values, presets and auto completion

        Options:
        * completion_items (List of completion items or
          dictionary of items and their titles)
        * preset_items (List of preset items or
          dictionary of items and their titles)
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

        self.list = gtk.ListStore(str)

        try:
            try:
                preset_items = self.preset_items.items()
                self.list = gtk.ListStore(str, str)
                text_renderer = self.widget.get_cells()[0]
                text_renderer.set_property('weight', pango.WEIGHT_BOLD)

                title_renderer = gtk.CellRendererText()
                self.widget.pack_start(title_renderer, expand=False)
                self.widget.add_attribute(title_renderer, 'text', 1)
            except AttributeError:
                preset_items = [[item] for item in self.preset_items]

            for preset in preset_items:
                self.list.append(preset)
        except AttributeError:
            pass

        self.widget.set_model(self.list)
        self.widget.set_text_column(0)

        try:
            completion = gtk.EntryCompletion()

            try:
                completion_items = self.completion_items.items()
                self.completion_list = gtk.ListStore(str, str)

                title_renderer = gtk.CellRendererText()
                completion.pack_end(title_renderer)
                completion.add_attribute(title_renderer, 'text', 1)
            except AttributeError:
                completion_items = [[item] for item in self.completion_items]
                self.completion_list = gtk.ListStore(str)

            keyword_renderer = gtk.CellRendererText()
            keyword_renderer.set_property('weight', pango.WEIGHT_BOLD)
            completion.pack_end(keyword_renderer)
            completion.add_attribute(keyword_renderer, 'text', 0)
            completion.set_match_func(self.on_matching)
            completion.connect('match-selected', self.on_match_selected)

            completion.set_popup_single_match(True)
            completion.set_model(self.completion_list)
            self.widget.child.set_completion(completion)

            for item in completion_items:
                self.completion_list.append(item)
        except AttributeError:
            pass

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        value = self.prefs.settings.get_option(self.name, self.default)
        self.widget.child.set_text(str(value))

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        return self.widget.child.get_text()

    def on_matching(self, completion, text, iter):
        """
            Matches the content of this box to
            the list of available completions
        """
        cursor_pos = self.widget.child.get_position()
        # Ignore the rest, allows for completions in the middle
        text = text[:cursor_pos]
        match = self.completion_list.get_value(iter, 0)

        # Try to find match, from largest to smallest
        for i in range(len(match), -1, -1):
            # Find from the rear
            match_pos = text.rfind(match[:i])
            # Matched if the match is not empty
            # and equal to the text from the matched position to the end
            # and not equal to the match itself
            # (the latter hides the match if it was already fully typed)
            if match[:i] and match[:i] == text[match_pos:] and match[:i] != match:
                return True
        return False

    def on_match_selected(self, completion, list, iter):
        """
            Inserts the selected completion
        """
        cursor_pos = self.widget.child.get_position()
        text = self.widget.child.get_text()[:cursor_pos]
        match = list.get_value(iter, 0)

        for i in range(len(match), -1, -1):
            match_pos = text.rfind(match[:i])
            if match[:i] and match[:i] == text[match_pos:]:
                # Delete halfway typed text
                self.widget.child.delete_text(
                    match_pos, match_pos + len(match[:i]))
                # Insert match at matched position
                self.widget.child.insert_text(
                    match, match_pos)
                # Update cursor position
                self.widget.child.set_position(match_pos + len(match))

        return True

