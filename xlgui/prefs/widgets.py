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

import gtk.gdk, hashlib, os, pango

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
        if hasattr(self, 'change'):
            self._setup_change()

    def _setup_change(self):
        """
            Sets up the function to be called when this preference is changed
        """
        self.widget.connect('focus-out-event',
            self.change, self.name, unicode(self.widget.get_text(), 'utf-8'))
        self.widget.connect('activate',
            lambda *e: self.change(self.widget, None, self.name,
                unicode(self.widget.get_text(), 'utf-8')))

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

        text = gtk.CellRendererText()
        available_tree = gtk.TreeView(self.available_list)
        available_col = gtk.TreeViewColumn(None, text, text=0)
        try:
            available_col.set_title(self.available_title)
        except AttributeError:
            pass
        available_tree.append_column(available_col)
        available_tree.set_reorderable(True)
        widget.pack_start(available_tree)

        selected_tree = gtk.TreeView(self.selected_list)
        selected_col = gtk.TreeViewColumn(None, text, text=0)
        try:
            selected_col.set_title(self.selected_title)
        except AttributeError:
            pass
        selected_tree.append_column(selected_col)
        selected_tree.set_reorderable(True)
        widget.pack_start(selected_tree)

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

        available_tree.connect('drag-data-received', self._drag_data_received)
        selected_tree.connect('drag-data-received', self._drag_data_received)

        widget.set_homogeneous(True)
        widget.set_spacing(6)

    def _drag_data_received(self, target_treeview, context, x, y, data, info, time):
        """
            Handles movement of rows
        """
        source_treeview = context.get_source_widget()
        source_list, path = source_treeview.get_selection().get_selected_rows()
        source_iter = source_list.get_iter(path[0])
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
            # Matched if not empty and match equal to
            # text from the matched position to the end
            if match[:i] and match[:i] == text[match_pos:]:
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

