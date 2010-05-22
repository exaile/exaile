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

import hashlib
import logging
import os

import glib
import gtk
import pango

from xl.nls import gettext as _
from xl import event, main, settings, xdg
from xlgui import commondialogs

logger = logging.getLogger(__name__)

class Preference(object):
    """
        Representing a gtk.Entry preferences item
    """
    default = ''
    restart_required = False

    def __init__(self, preferences, widget):
        """
            Initializes the preferences item
            expects the name of the widget in the designer file, the default for
            this setting, an optional function to be called when the value is
            changed, and an optional function to be called when this setting
            is applied
        """

        self.widget = widget
        self.preferences = preferences

        if self.restart_required:
            self.message = commondialogs.MessageBar(
                parent=preferences.builder.get_object('preferences_box'),
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_CLOSE,
                text=_('Restart Exaile?'))
            self.message.set_secondary_text(
                _('A restart is required for this change to take effect.'))

            button = self.message.add_button(_('Restart'), gtk.RESPONSE_ACCEPT)
            button.set_image(gtk.image_new_from_stock(
                gtk.STOCK_REFRESH, gtk.ICON_SIZE_BUTTON))

            self.message.connect('response', self.on_message_response)

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
            logger.error("Widget not found: %s" % (self.name))
            return
        self.widget.set_text(str(self.preferences.settings.get_option(
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
        if hasattr(self, 'done') and not self.done():
            return False

        oldvalue = self.preferences.settings.get_option(self.name, self.default)

        if value is None:
            value = self._get_value()

        if value != oldvalue:
            self.preferences.settings.set_option(self.name, value)

            if self.restart_required:
                self.message.show()

        return True

    def on_message_response(self, widget, response):
        """
            Restarts Exaile if requested
        """
        widget.hide()

        if response == gtk.RESPONSE_ACCEPT:
            glib.idle_add(main.exaile().quit, True)

class Conditional(object):
    """
        Allows for reactions on changes
        of other preference items
    """
    condition_preference_name = ''
    condition_widget = None

    def __init__(self):
        event.add_callback(self.on_option_set, 'option_set')
        glib.idle_add(self.on_option_set,
            'option_set', settings, self.condition_preference_name)

    def on_check_condition(self):
        """
            Specifies the condition to meet

            :returns: Whether the condition is met or not
            :rtype: bool
        """
        pass

    def on_condition_met(self):
        """
            Called as soon as the
            specified condition is met
        """
        self.widget.set_sensitive(True)

    def on_condition_failed(self):
        """
            Called as soon as the specified
            condition is not met anymore
        """
        self.widget.set_sensitive(False)

    def on_option_set(self, event, settings, option):
        """
            Called as soon as options change
        """
        if option == self.condition_preference_name:
            if self.on_check_condition():
                self.on_condition_met()
            else:
                self.on_condition_failed()

class CheckConditional(Conditional):
    """
        True if the conditional widget is active
    """
    def on_check_condition(self):
        """
            Specifies the condition to meet

            :returns: Whether the condition is met or not
            :rtype: bool
        """
        return self.condition_widget.get_active()

class HashedPreference(Preference):
    """
        Represents a text entry with automated hashing

        Options:
        * type (Which hashfunction to use, default: md5)
    """
    type = 'md5'

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

        self.widget.set_visibility(True)
        self._delete_text_id = self.widget.connect('delete-text',
            self.on_delete_text)
        self._insert_text_id = self.widget.connect('insert-text',
            self.on_insert_text)

    def _setup_change(self):
        """
            Sets up the function to be called when this preference is changed
        """
        self.widget.connect('focus-out-event', lambda *e: self.apply())

    def done(self):
        """
            Determines if changes are to be expected
        """
        if self._delete_text_id is None and \
           self._insert_text_id is None:
            return True

        return False

    def apply(self, value=None):
        """
            Applies this setting
        """
        if not self.done():
            return False

        if value is None:
            value = self._get_value()
        if value is None:
            return True

        if value != '':
            hashfunc = hashlib.new(self.type)
            hashfunc.update(value)
            value = hashfunc.hexdigest()

        oldvalue = self.preferences.settings.get_option(self.name, self.default)

        if value != oldvalue:
            self.preferences.settings.set_option(self.name, value)

        self.widget.set_text(value)
        self.widget.set_visibility(True)
        self._delete_text_id = self.widget.connect('delete-text',
            self.on_delete_text)
        self._insert_text_id = self.widget.connect('insert-text',
            self.on_insert_text)

        return True

    def on_delete_text(self, widget, start, end):
        """
            Clears the text entry and makes following input invisible
        """
        self.widget.disconnect(self._delete_text_id)
        self.widget.disconnect(self._insert_text_id)
        self._delete_text_id = self._insert_text_id = None

        self.widget.set_visibility(False)
        self.widget.set_text('')

    def on_insert_text(self, widget, text, length, position):
        """
            Clears the text entry and makes following input invisible
        """
        self.widget.disconnect(self._delete_text_id)
        self.widget.disconnect(self._insert_text_id)
        self._delete_text_id = self._insert_text_id = None

        self.widget.set_visibility(False)
        # Defer to after returning from this method
        glib.idle_add(self.widget.set_text, text)
        glib.idle_add(self.widget.set_position, length)

class CheckPreference(Preference):
    """
        A class to represent check boxes in the preferences window
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('toggled',
            self.change)

    def _set_value(self):
        self.widget.set_active(
            self.preferences.settings.get_option(self.name,
            self.default))

    def _get_value(self):
        return self.widget.get_active()

class DirPreference(Preference):
    """
        Directory chooser button
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        pass

    def _set_value(self):
        """
            Sets the current directory
        """
        directory = os.path.expanduser(
            self.preferences.settings.get_option(self.name, self.default))
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.widget.set_current_folder(directory)

    def _get_value(self):
        return self.widget.get_filename()

class OrderListPreference(Preference):
    """
        A list box with reorderable items
    """
    def __init__(self, preferences, widget):
        self.model = gtk.ListStore(str)
        self.items = []
        Preference.__init__(self, preferences, widget)
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
        items = self.preferences.settings.get_option(self.name,
            self.default)

        self.model.clear()
        for item in items:
            self.model.append([item])

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        self.items = []

        for row in self.model:
            self.items += [row[0]]

        return items

class SelectionListPreference(Preference):
    """
        Two list boxes allowing to drag items
        to each other, reorderable

        Options:
        * available_title (Title of the list of available items)
        * selected_title (Title of the list of selected items)
        * available_items (Dictionary of items and their titles)
        * fixed_items (Dictionary of non-removable items and their titles)
    """
    def __init__(self, preferences, widget):
        self.available_list = gtk.ListStore(str)
        self.selected_list = gtk.ListStore(str)
        self._update_lists(self.default)

        # Make sure container is empty
        for child in widget.get_children():
            widget.remove(child)

        Preference.__init__(self, preferences, widget)
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

        self.add_button = gtk.Button()
        self.add_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_BUTTON))
        self.add_button.set_tooltip_text(_('Add item'))
        self.add_button.set_sensitive(False)
        self.remove_button = gtk.Button()
        self.remove_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_BACK, gtk.ICON_SIZE_BUTTON))
        self.remove_button.set_tooltip_text(_('Remove item'))
        self.remove_button.set_sensitive(False)

        control_box = gtk.VBox(spacing=3)
        control_box.pack_start(self.add_button, expand=False)
        control_box.pack_start(self.remove_button, expand=False)
        control_panel = gtk.Alignment(xalign=0.5, yalign=0.5,
            xscale=0.0, yscale=0.0)
        control_panel.add(control_box)

        self.up_button = gtk.Button()
        self.up_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_UP, gtk.ICON_SIZE_BUTTON))
        self.up_button.set_tooltip_text(_('Move selected item up'))
        self.up_button.set_sensitive(False)
        self.down_button = gtk.Button()
        self.down_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_GO_DOWN, gtk.ICON_SIZE_BUTTON))
        self.down_button.set_tooltip_text(_('Move selected item down'))
        self.down_button.set_sensitive(False)

        move_box = gtk.VBox(spacing=3)
        move_box.pack_start(self.up_button, expand=False)
        move_box.pack_start(self.down_button, expand=False)
        move_panel = gtk.Alignment(xalign=0.5, yalign=0.5, xscale=0.0, yscale=0.0)
        move_panel.add(move_box)

        available_scrollwindow = gtk.ScrolledWindow()
        available_scrollwindow.set_property('shadow-type', gtk.SHADOW_IN)
        available_scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        available_scrollwindow.add(available_tree)

        selected_scrollwindow = gtk.ScrolledWindow()
        selected_scrollwindow.set_property('shadow-type', gtk.SHADOW_IN)
        selected_scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        selected_scrollwindow.add(selected_tree)

        widget.pack_start(available_scrollwindow)
        widget.pack_start(control_panel, expand=False)
        widget.pack_start(selected_scrollwindow)
        widget.pack_start(move_panel, expand=False)

        self.add_button.connect('clicked', self.on_add_button_clicked)
        self.remove_button.connect('clicked', self.on_remove_button_clicked)
        self.up_button.connect('clicked', self.on_up_button_clicked)
        self.down_button.connect('clicked', self.on_down_button_clicked)

        self.available_selection.connect('changed',
            self.on_available_selection_changed)
        self.selected_selection.connect('changed',
            self.on_selected_selection_changed)

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

        available_tree.connect('drag-data-received',
            self.on_drag_data_received)
        available_tree.connect('key-press-event',
            self.on_available_tree_key_pressed)
        available_tree.connect('button-press-event',
            self.on_available_tree_button_press_event)
        selected_tree.connect('drag-data-received',
            self.on_drag_data_received)
        selected_tree.connect('key-press-event',
            self.on_selected_tree_key_pressed)
        selected_tree.connect('button-press-event',
            self.on_selected_tree_button_press_event)

        self.available_list.connect('row-inserted',
            self.on_available_list_row_inserted, available_tree)
        self.selected_list.connect('row-inserted',
            self.on_selected_list_row_inserted, selected_tree)

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

    def _setup_change(self):
        """
            Sets up the function to be called
            when this preference is changed
        """
        self.selected_list.connect('row-deleted', self.change)
        self.selected_list.connect('row-inserted', self.change)
        self.selected_list.connect('rows-reordered', self.change)

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        items = self.preferences.settings.get_option(self.name, self.default)
        self._update_lists(items)

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        items = []

        for row in self.selected_list:
            selected_value = row[0]

            for id, title in self.available_items.iteritems():
                if selected_value == title:
                    items.append(id)
                    break

        return items

    def on_available_selection_changed(self, selection):
        """
            Enables buttons based on the current selection
        """
        row_selected = (selection.count_selected_rows() > 0)
        self.add_button.set_sensitive(row_selected)

    def on_selected_selection_changed(self, selection):
        """
            Enables buttons based on the current selection
        """
        row_selected = (selection.count_selected_rows() > 0)

        self.remove_button.set_sensitive(row_selected)

        if row_selected:
            first_iter = self.selected_list.get_iter_first()
            last_iter = None

            for row in self.selected_list:
                last_iter = row.iter

            first_selected = selection.iter_is_selected(first_iter)
            last_selected = selection.iter_is_selected(last_iter)

            self.up_button.set_sensitive(not first_selected)
            self.down_button.set_sensitive(not last_selected)

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
        self.on_selected_selection_changed(self.selected_selection)

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
        self.on_selected_selection_changed(self.selected_selection)

    def on_available_tree_key_pressed(self, tree, event):
        """
            Handles moving of items via keyboard interaction
        """
        if not event.state & gtk.gdk.MOD1_MASK: return

        if event.keyval == gtk.keysyms.Right:
            self.on_add_button_clicked(None)

    def on_selected_tree_key_pressed(self, tree, event):
        """
            Handles moving of items via keyboard interaction
        """
        if not event.state & gtk.gdk.MOD1_MASK: return

        if event.keyval == gtk.keysyms.Left:
            self.on_remove_button_clicked(None)
        elif event.keyval == gtk.keysyms.Up:
            self.on_up_button_clicked(None)
        elif event.keyval == gtk.keysyms.Down:
            self.on_down_button_clicked(None)

    def on_available_tree_button_press_event(self, tree, event):
        """
            Adds items on double click
        """
        if not tree.get_path_at_pos(int(event.x), int(event.y)):
            return

        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.on_add_button_clicked(None)

    def on_selected_tree_button_press_event(self, tree, event):
        """
            Removes items on double click
        """
        if not tree.get_path_at_pos(int(event.x), int(event.y)):
            return

        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.on_remove_button_clicked(None)

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

class ShortcutListPreference(Preference):
    """
        A list showing available items and allowing
        to assign/edit/remove key accelerators
    """
    def __init__(self, preferences, widget):
        self.list = gtk.ListStore(str, str)

        Preference.__init__(self, preferences, widget)

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
        items = self.preferences.settings.get_option(self.name, self.default)
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

class TextViewPreference(Preference):
    """
        Represents a gtk.TextView
    """
    def __init__(self, preferences, widget):
        """
            Initializes the object
        """
        Preference.__init__(self, preferences, widget)

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
            self.preferences.settings.get_option(self.name,
            default=self.default)))

    def _get_value(self):
        """
            Applies the setting
        """
        return self.get_all_text()

class ListPreference(Preference):
    """
        A class to represent a space separated list in the preferences window
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _set_value(self):
        items = self.preferences.settings.get_option(self.name,
            default=self.default)
        try:
            items = " ".join(items)
        except:
            items = ""
        self.widget.set_text(items)

    def _get_value(self):
        # shlex is broken with unicode, so we feed it UTF-8 and decode
        # afterwards.
        import shlex
        values = shlex.split(self.widget.get_text())
        values = [unicode(value, 'utf-8') for value in values]
        return values

class SpinPreference(Preference):
    """
        A class to represent a numeric entry box with stepping buttons
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _set_value(self):
        value = self.preferences.settings.get_option(self.name,
            default=self.default)
        self.widget.set_value(value)

    def _setup_change(self):
        self.widget.connect('value-changed', self.change)

    def _get_value(self):
        return self.widget.get_value()

class ScalePreference(SpinPreference):
    """
        Representation of gtk.Scale widgets
    """
    def __init__(self, preferences, widget):
        SpinPreference.__init__(self, preferences, widget)

class FloatPreference(Preference):
    """
        A class to represent a floating point number in the preferences window
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _set_value(self):
        self.widget.set_text(str(
            self.preferences.settings.get_option(self.name,
            default=self.default)))

    def _get_value(self):
        return float(self.widget.get_text())

class IntPreference(FloatPreference):

    def _get_value(self):
        return int(self.widget.get_text())

class ColorButtonPreference(Preference):
    """
        A class to represent the color button in the preferences window
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('color-set', self.change)

    def _set_value(self):
        self.widget.set_color(gtk.gdk.color_parse(
            self.preferences.settings.get_option(self.name,
            self.default)))

    def _get_value(self):
        color = self.widget.get_color()
        string = "#%.2x%.2x%.2x" % (color.red / 257, color.green / 257,
            color.blue / 257)
        return string

class FontButtonPreference(ColorButtonPreference):
    """
        Font button
    """
    def __init__(self, preferences, widget):
        ColorButtonPreference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('font-set', self.change)

    def _set_value(self):
        font = self.preferences.settings.get_option(self.name,
            self.default)
        self.widget.set_font_name(font)

    def _get_value(self):
        font = self.widget.get_font_name()
        return font

class ComboPreference(Preference):
    """
        A combo box
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('changed', self.change)

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        item = self.preferences.settings.get_option(self.name,
            self.default)

        model = self.widget.get_model()

        for row in model:
            if item == row[0]:
                self.widget.set_active_iter(row.iter)

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        model = self.widget.get_model()
        iter = self.widget.get_active_iter()

        return model.get_value(iter, 0)

class ComboEntryPreference(Preference):
    """
        A combo box allowing for user defined
        values, presets and auto completion

        Options:
        * completion_items (List of completion items or
          dictionary of items and their titles)
        * preset_items (List of preset items or
          dictionary of items and their titles)
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

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

    def _setup_change(self):
        """
            Sets up the function to be called
            when this preference is changed
        """
        self.widget.connect('changed', self.change, self.name,
            self._get_value())

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        value = self.preferences.settings.get_option(self.name, self.default)
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

# vim: et sts=4 sw=4
