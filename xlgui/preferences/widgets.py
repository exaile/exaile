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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
from typing import Any, Callable, Optional

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from xl.nls import gettext as _
from xl import event, main, settings
from xlgui import guiutil
from xlgui.widgets import dialogs
from xlgui.guiutil import GtkTemplate

logger = logging.getLogger(__name__)


class Preference:
    """
    Representing a Gtk.Entry preferences item
    """

    default: Any = ''
    done: Callable[[], bool]
    label_widget: Optional[Gtk.Widget]
    name: str
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
            self.message = dialogs.MessageBar(
                parent=preferences.builder.get_object('preferences_box'),
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.CLOSE,
                text=_('Restart Exaile?'),
            )
            self.message.set_secondary_text(
                _('A restart is required for this change to take effect.')
            )

            button = self.message.add_button(_('Restart'), Gtk.ResponseType.ACCEPT)
            button.set_image(
                Gtk.Image.new_from_icon_name('view-refresh', Gtk.IconSize.BUTTON)
            )

            self.message.connect('response', self.on_message_response)

        self._set_value()
        self._setup_change()

    def change(self, *args):
        self.apply()

    def _setup_change(self):
        """
        Sets up the function to be called when this preference is changed
        """
        self.widget.connect(
            'focus-out-event', self.change, self.name, self._get_value()
        )

        try:
            self.widget.connect(
                'activate',
                lambda *e: self.change(self.widget, None, self.name, self._get_value()),
            )
        except TypeError:
            pass

    def _get_value(self):
        """
        Value to be stored into the settings file
        """
        return self.widget.get_text()

    def _set_value(self):
        """
        Sets the GUI widget up for this preference
        """
        if not self.widget:
            logger.error("Widget not found: %s", self.name)
            return
        self.widget.set_text(str(settings.get_option(self.name, self.default)))

    def apply(self, value=None):
        """
        Applies this setting
        """
        if hasattr(self, 'done') and not self.done():
            return False

        oldvalue = settings.get_option(self.name, self.default)

        if value is None:
            value = self._get_value()

        if value != oldvalue:
            settings.set_option(self.name, value)

            if self.restart_required:
                self.message.show()

        return True

    def on_message_response(self, widget, response):
        """
        Restarts Exaile if requested
        """
        widget.hide()

        if response == Gtk.ResponseType.ACCEPT:
            GLib.idle_add(main.exaile().quit, True)

    def hide_widget(self):
        '''Hides the widget and optionally its associated label'''
        self.widget.hide()
        if hasattr(self, 'label_widget'):
            self.label_widget.hide()

    def show_widget(self):
        '''Shows the widget and optionally its associated label'''
        self.widget.show_all()
        if hasattr(self, 'label_widget'):
            self.label_widget.show_all()

    def set_widget_sensitive(self, value):
        '''Sets sensitivity of widget and optionally its associated label'''
        self.widget.set_sensitive(value)
        if hasattr(self, 'label_widget'):
            self.label_widget.set_sensitive(value)


class Conditional:
    """
    Allows for reactions on changes
    of other preference items
    """

    condition_preference_name = ''
    condition_widget = None

    def __init__(self):
        event.add_ui_callback(self.on_option_set, 'option_set')
        GLib.idle_add(
            self.on_option_set, 'option_set', settings, self.condition_preference_name
        )

    def get_condition_value(self):
        """
        :returns: The currently selected value in the condition widget,
                  presumes it is a combo box
        """
        i = self.condition_widget.get_active_iter()
        return self.condition_widget.get_model().get_value(i, 0)

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

    def get_condition_value(self):
        return self.condition_widget.get_active()

    def on_check_condition(self):
        """
        Specifies the condition to meet

        :returns: Whether the condition is met or not
        :rtype: bool
        """
        return self.get_condition_value()


class MultiConditional:
    """
    Allows for reactions on changes of multiple preference items
    """

    condition_preference_names = []
    condition_widgets = {}

    def __init__(self):
        event.add_ui_callback(self.on_option_set, 'option_set')
        GLib.idle_add(
            self.on_option_set,
            'option_set',
            settings,
            self.condition_preference_names[0],
        )

    def get_condition_value(self, name):
        """
        :returns: The currently selected value in the condition widget,
                  presumes it is a combo box
        """
        widget = self.condition_widgets[name]
        return widget.get_model().get_value(widget.get_active_iter(), 0)

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
        if option in self.condition_preference_names:
            if self.on_check_condition():
                self.on_condition_met()
            else:
                self.on_condition_failed()


class Button(Preference):
    """
    Represents a button for custom usage
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

        widget.connect('clicked', self.on_clicked)

    def _setup_change(self, *e):
        pass

    def _get_value(self):
        return None

    def _set_value(self):
        pass

    def apply(self, *e):
        return False

    def on_clicked(self, button):
        """Override"""
        pass


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
        self._delete_text_id = self.widget.connect('delete-text', self.on_delete_text)
        self._insert_text_id = self.widget.connect('insert-text', self.on_insert_text)

    def _setup_change(self):
        """
        Sets up the function to be called when this preference is changed
        """
        self.widget.connect('focus-out-event', lambda *e: self.apply())

    def done(self):
        """
        Determines if changes are to be expected
        """
        if self._delete_text_id is None and self._insert_text_id is None:
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
            hashfunc.update(value.encode('utf-8'))
            value = hashfunc.hexdigest()

        oldvalue = settings.get_option(self.name, self.default)

        if value != oldvalue:
            settings.set_option(self.name, value)

        self.widget.set_text(value)
        self.widget.set_visibility(True)
        self._delete_text_id = self.widget.connect('delete-text', self.on_delete_text)
        self._insert_text_id = self.widget.connect('insert-text', self.on_insert_text)

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
        GLib.idle_add(self.widget.set_text, text)
        GLib.idle_add(self.widget.set_position, length)


class CheckPreference(Preference):
    """
    A class to represent check boxes in the preferences window
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('toggled', self.change)

    def _set_value(self):
        self.widget.set_active(settings.get_option(self.name, self.default))

    def _get_value(self):
        return self.widget.get_active()


class DirPreference(Preference):
    """
    Directory chooser button
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('current-folder-changed', self.change)

    def _set_value(self):
        """
        Sets the current directory
        """
        directory = os.path.expanduser(settings.get_option(self.name, self.default))
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
        self.model = Gtk.ListStore(str)
        Preference.__init__(self, preferences, widget)
        widget.set_headers_visible(False)
        widget.set_reorderable(True)

        text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("Item", text, text=0)
        self.widget.append_column(col)
        self.widget.set_model(self.model)

    def _setup_change(self):
        self.widget.connect('drag-end', self.change)

    def _set_value(self):
        """
        Sets the preferences for this widget
        """
        items = settings.get_option(self.name, self.default)

        self.model.clear()
        for item in items:
            self.model.append([item])

    def _get_value(self):
        """
        Value to be stored into the settings file
        """
        items = []

        for row in self.model:
            items += [row[0]]

        return items


class SelectionListPreference(Preference):
    """
    A list allowing for enabling/disabling
    as well as reordering of items

    Options:
    * items: list of :class:`SelectionListPreference.Item` objects
    * default: list of item ids
    """

    class Item:
        """
        Convenience class for preference item description
        """

        def __init__(self, id, title, description=None, fixed=False):
            """
            :param id: the unique identifier
            :type id: string
            :param title: the readable title
            :type title: string
            :param description: optional description of the item
            :type description: string
            :param fixed: whether the item should be removable
            :type fixed: bool
            """
            self.__id = id
            self.__title = title
            self.__description = description
            self.__fixed = fixed

        id = property(lambda self: self.__id)
        title = property(lambda self: self.__title)
        description = property(lambda self: self.__description)
        fixed = property(lambda self: self.__fixed)

    @GtkTemplate('ui', 'preferences', 'widgets', 'selection_list_preference.ui')
    class InternalWidget(Gtk.ScrolledWindow):
        """
        Internal class for making GtkTemplate work with subclassing
        """

        __gtype_name__ = 'InternalWidget'

        (
            model,
            tree,
            toggle_renderer,
            text_renderer,
            enabled_column,
            title_column,
        ) = GtkTemplate.Child.widgets(6)
        selectionlp = None

        def __init__(self, preference):
            Gtk.ScrolledWindow.__init__(self)
            self.init_template()
            self.selectionlp = preference

            self.tree.enable_model_drag_source(
                Gdk.ModifierType.BUTTON1_MASK,
                [('GTK_TREE_MODEL_ROW', Gtk.TargetFlags.SAME_WIDGET, 0)],
                Gdk.DragAction.MOVE,
            )
            self.tree.enable_model_drag_dest(
                [('GTK_TREE_MODEL_ROW', Gtk.TargetFlags.SAME_WIDGET, 0)],
                Gdk.DragAction.MOVE,
            )
            self.tree.connect('drag-end', self.selectionlp.change)

            self.enabled_column.set_cell_data_func(
                self.toggle_renderer, self.enabled_data_function
            )

            self.title_column.set_cell_data_func(
                self.text_renderer, self.title_data_function
            )

        @GtkTemplate.Callback
        def on_row_activated(self, tree, path, column):
            """
            Updates the enabled column
            """
            if self.model[path][4]:
                return

            enabled = not self.model[path][3]
            self.model[path][3] = enabled

        def enabled_data_function(self, column, cell, model, iter, user_data):
            """
            Prepares sensitivity
            of the enabled column
            """
            path = model.get_path(iter)
            fixed = model[path][4]
            cell.props.sensitive = not fixed

        def title_data_function(self, column, cell, model, iter, user_data):
            """
            Prepares the markup to be
            used for the title column
            """
            path = model.get_path(iter)
            title, description = model[path][1], model[path][2]

            markup = '<b>%s</b>' % title

            if description is not None:
                markup += '\n<span size="small">%s</span>' % description

            cell.props.markup = markup

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

        @GtkTemplate.Callback
        def on_key_press_event(self, tree, event):
            """
            Allows for reordering via keyboard (Alt+<direction>)
            """
            if not event.get_state() & Gdk.ModifierType.MOD1_MASK:
                return

            if event.keyval not in (Gdk.KEY_Up, Gdk.KEY_Down):
                return

            model, selected_iter = tree.get_selection().get_selected()

            if event.keyval == Gdk.KEY_Up:
                previous_iter = self.iter_prev(selected_iter, model)
                model.move_before(selected_iter, previous_iter)
            elif event.keyval == Gdk.KEY_Down:
                next_iter = model.iter_next(selected_iter)
                model.move_after(selected_iter, next_iter)

            tree.scroll_to_cell(model.get_path(selected_iter))

            self.selectionlp.apply()

        @GtkTemplate.Callback
        def on_toggled(self, cell, path):
            """
            Updates the enabled column
            """
            if self.model[path][4]:
                return

            active = not cell.get_active()
            cell.set_active(active)
            self.model[path][3] = active

            self.selectionlp.apply()

    def __init__(self, preferences, widget):
        internal_widget = self.InternalWidget(self)
        self.model = internal_widget.model

        for item in self.items:
            row = [item.id, item.title, item.description, True, item.fixed]
            self.model.append(row)

        guiutil.gtk_widget_replace(widget, internal_widget)
        Preference.__init__(self, preferences, internal_widget)

    def _get_value(self):
        """
        Value to be stored in the settings
        """
        return [row[0] for row in self.model if row[3]]

    def _set_value(self):
        """
        Updates the internal representation
        """
        selected_items = settings.get_option(self.name, self.default)
        # Get list of available items
        available_items = [row[0] for row in self.model]

        if not available_items:
            return

        # Filter out invalid items
        selected_items = [item for item in selected_items if item in available_items]
        # Cut out unselected items
        unselected_items = [
            item for item in available_items if item not in selected_items
        ]
        # Move unselected items to the end
        items = selected_items + unselected_items
        new_order = [available_items.index(item) for item in items]
        self.model.reorder(new_order)

        # Disable unselected items
        for row in self.model:
            if row[0] in unselected_items and not row[4]:
                row[3] = False
            else:
                row[3] = True


class ShortcutListPreference(Preference):
    """
    A list showing available items and allowing
    to assign/edit/remove key accelerators
    """

    def __init__(self, preferences, widget):
        self.list = Gtk.ListStore(str, str)

        Preference.__init__(self, preferences, widget)

        self.widget.set_model(self.list)

        title_renderer = Gtk.CellRendererText()
        title_column = Gtk.TreeViewColumn(_('Action'), title_renderer, text=0)
        title_column.set_expand(True)
        title_column.set_cell_data_func(title_renderer, self.title_data_func)
        accel_renderer = Gtk.CellRendererAccel()
        accel_renderer.set_property('editable', True)
        accel_renderer.set_property('style', Pango.Style.OBLIQUE)
        accel_renderer.connect('accel-cleared', self.on_accel_cleared)
        accel_renderer.connect('accel-edited', self.on_accel_edited)
        accel_column = Gtk.TreeViewColumn(_('Shortcut'), accel_renderer, text=1)
        accel_column.set_expand(True)

        self.widget.append_column(title_column)
        self.widget.append_column(accel_column)

    def title_data_func(self, celllayout, cell, model, iter, user_data):
        """
        Renders human readable titles instead of the actual keys
        """
        key = model.get_value(iter, 0)

        try:
            cell.set_property('text', self.available_items[key])
        except KeyError:
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
        accel = Gtk.accelerator_name(accel_key, accel_mods)
        iter = self.list.get_iter(path)
        self.list.set_value(iter, 1, accel)

    def _set_value(self):
        """
        Sets the preferences for this widget
        """
        items = settings.get_option(self.name, self.default)
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
        for action in self.available_items.keys():
            try:
                accel = items[action]
            except KeyError:
                accel = ''
            self.list.append([action, accel])


class TextViewPreference(Preference):
    """
    Represents a Gtk.TextView
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
        return buf.get_text(start, end, True)

    def _set_value(self):
        """
        Sets the value of this widget
        """
        self.widget.get_buffer().set_text(
            str(settings.get_option(self.name, default=self.default))
        )

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
        items = settings.get_option(self.name, default=self.default)
        try:
            items = " ".join(items)
        except TypeError:
            items = ""
        self.widget.set_text(items)

    def _get_value(self):
        import shlex

        return shlex.split(self.widget.get_text())


class SpinPreference(Preference):
    """
    A class to represent a numeric entry box with stepping buttons
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _set_value(self):
        value = settings.get_option(self.name, default=self.default)
        self.widget.set_value(value)

    def _setup_change(self):
        self.widget.connect('value-changed', self.change)

    def _get_value(self):
        return self.widget.get_value()


class ScalePreference(SpinPreference):
    """
    Representation of Gtk.Scale widgets
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
        self.widget.set_text(str(settings.get_option(self.name, default=self.default)))

    def _get_value(self):
        return float(self.widget.get_text())


class IntPreference(FloatPreference):
    def _get_value(self):
        return int(self.widget.get_text())


class RGBAButtonPreference(Preference):
    """
    A class to represent the color button
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('color-set', self.change)

    def _set_value(self):
        value = settings.get_option(self.name, self.default)
        rgba = Gdk.RGBA()
        rgba.parse(value)
        self.widget.set_rgba(rgba)

    def _get_value(self):
        return self.widget.get_rgba().to_string()


class FontButtonPreference(Preference):
    """
    Font button
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('font-set', self.change)

    def _set_value(self):
        font = settings.get_option(self.name, self.default)
        self.widget.set_font_name(font)

    def _get_value(self):
        font = self.widget.get_font_name()
        return font


class FontResetButtonPreference(Button, Conditional):
    """
    A button to reset a font button to a default font
    """

    def __init__(self, preferences, widget):
        Button.__init__(self, preferences, widget)
        Conditional.__init__(self)

    def on_check_condition(self):
        if self.condition_widget.get_font_name() == self.default:
            return False
        return True

    def on_clicked(self, button):
        self.condition_widget.set_font_name(self.default)
        self.condition_widget.emit('font-set')


class ComboPreference(Preference):
    """
    A combo box. The value stored in the settings must be the
    first column of the combo box model.
    """

    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('changed', self.change)

    def _set_value(self):
        """
        Sets the preferences for this widget
        """
        item = settings.get_option(self.name, self.default)

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

        self.list = Gtk.ListStore(str)

        try:
            try:
                preset_items = list(self.preset_items.items())
                self.list = Gtk.ListStore(str, str)
                text_renderer = self.widget.get_cells()[0]
                text_renderer.set_property('weight', Pango.Weight.BOLD)

                title_renderer = Gtk.CellRendererText()
                self.widget.pack_start(title_renderer, False)
                self.widget.add_attribute(title_renderer, 'text', 1)
            except AttributeError:
                preset_items = [[item] for item in self.preset_items]

            for preset in preset_items:
                self.list.append(preset)
        except AttributeError:
            pass

        self.widget.set_model(self.list)
        self.widget.set_entry_text_column(0)

        try:
            completion = Gtk.EntryCompletion()

            try:
                completion_items = list(self.completion_items.items())
                self.completion_list = Gtk.ListStore(str, str)

                title_renderer = Gtk.CellRendererText()
                completion.pack_end(title_renderer, True)
                completion.add_attribute(title_renderer, 'text', 1)
            except AttributeError:
                completion_items = [[item] for item in self.completion_items]
                self.completion_list = Gtk.ListStore(str)

            keyword_renderer = Gtk.CellRendererText()
            keyword_renderer.set_property('weight', Pango.Weight.BOLD)
            completion.pack_end(keyword_renderer, True)
            completion.add_attribute(keyword_renderer, 'text', 0)
            completion.set_match_func(self.on_matching)
            completion.connect('match-selected', self.on_match_selected)

            completion.set_popup_single_match(True)
            completion.set_model(self.completion_list)
            self.widget.get_child().set_completion(completion)

            for item in completion_items:
                self.completion_list.append(item)
        except AttributeError:
            pass

    def _setup_change(self):
        """
        Sets up the function to be called
        when this preference is changed
        """
        self.widget.connect('changed', self.change, self.name, self._get_value())

    def _set_value(self):
        """
        Sets the preferences for this widget
        """
        value = settings.get_option(self.name, self.default)
        self.widget.get_child().set_text(str(value))

    def _get_value(self):
        """
        Value to be stored into the settings file
        """
        return self.widget.get_child().get_text()

    def on_matching(self, completion, text, iter):
        """
        Matches the content of this box to
        the list of available completions
        """
        cursor_pos = self.widget.get_child().get_position()
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
        cursor_pos = self.widget.get_child().get_position()
        text = self.widget.get_child().get_text()[:cursor_pos]
        match = list.get_value(iter, 0)

        for i in range(len(match), -1, -1):
            match_pos = text.rfind(match[:i])
            if match[:i] and match[:i] == text[match_pos:]:
                # Delete halfway typed text
                self.widget.get_child().delete_text(
                    match_pos, match_pos + len(match[:i])
                )
                # Insert match at matched position
                self.widget.get_child().insert_text(match, match_pos)
                # Update cursor position
                self.widget.get_child().set_position(match_pos + len(match))

        return True


# vim: et sts=4 sw=4
