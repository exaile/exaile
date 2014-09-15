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

import glib
import gtk
import pango

from xl.nls import gettext as _
from xl import event, main, settings, xdg
from xlgui import guiutil
from xlgui.widgets import dialogs

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
            self.message = dialogs.MessageBar(
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

    def _get_value(self):
        """
            Value to be stored into the settings file
        """
        return unicode(self.widget.get_text(), 'utf-8')

    def _set_value(self):
        """
            Sets the GUI widget up for this preference
        """
        if not self.widget:
            logger.error("Widget not found: %s" % (self.name))
            return
        self.widget.set_text(str(self.preferences.settings.get_option(
            self.name, self.default)))

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

class MultiConditional(object):
    """
        Allows for reactions on changes of multiple preference items
    """
    condition_preference_names = []
    condition_widgets = {}

    def __init__(self):
        event.add_callback(self.on_option_set, 'option_set')
        glib.idle_add(self.on_option_set,
            'option_set', settings, self.condition_preference_names[0])

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

    def _setup_change(*e):
        pass

    def _get_value(self):
        return None

    def _set_value(self):
        pass

    def apply(*e):
        return False

    def on_clicked(self, button):
        """ Override """
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
        self.widget.connect('current-folder-changed', self.change)

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
    class Item(object):
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

    def __init__(self, preferences, widget):
        self.model = gtk.ListStore(
            str,  # 0: item
            str,  # 1: title
            str,  # 2: description
            bool, # 3: enabled
            bool  # 4: fixed
        )
        
        for item in self.items:
            self.model.append([item.id, item.title, item.description,
                True, item.fixed])

        tree = gtk.TreeView(self.model)
        tree.set_headers_visible(False)
        tree.set_rules_hint(True)
        tree.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK,
            [('GTK_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
            gtk.gdk.ACTION_MOVE
        )
        tree.enable_model_drag_dest(
            [('GTK_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
            gtk.gdk.ACTION_MOVE
        )
        tree.connect('row-activated', self.on_row_activated)
        tree.connect('key-press-event', self.on_key_press_event)
        tree.connect('drag-end', self.change)

        toggle_renderer = gtk.CellRendererToggle()
        toggle_renderer.connect('toggled', self.on_toggled)
        enabled_column = gtk.TreeViewColumn('Enabled', toggle_renderer, active=3)
        enabled_column.set_cell_data_func(toggle_renderer,
            self.enabled_data_function)
        tree.append_column(enabled_column)

        text_renderer = gtk.CellRendererText()
        text_renderer.props.ypad = 6
        title_column = gtk.TreeViewColumn('Title', text_renderer, text=1)
        title_column.set_cell_data_func(text_renderer,
            self.title_data_function)
        tree.append_column(title_column)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add(tree)

        guiutil.gtk_widget_replace(widget, scroll)
        Preference.__init__(self, preferences, scroll)

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
        selected_items = [item for item in selected_items \
            if item in available_items]
        # Cut out unselected items
        unselected_items = [item for item in available_items \
            if item not in selected_items]
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

    def on_row_activated(self, tree, path, column):
        """
            Updates the enabled column
        """
        model = tree.get_model()

        if model[path][4]:
            return

        enabled = not model[path][3]
        model[path][3] = enabled

    def on_key_press_event(self, tree, event):
        """
            Allows for reordering via keyboard (Alt+<direction>)
        """
        if not event.state & gtk.gdk.MOD1_MASK:
            return

        if event.keyval not in (gtk.keysyms.Up, gtk.keysyms.Down):
            return

        model, selected_iter = tree.get_selection().get_selected()

        if event.keyval == gtk.keysyms.Up:
            previous_iter = self.iter_prev(selected_iter, model)
            model.move_before(selected_iter, previous_iter)
        elif event.keyval == gtk.keysyms.Down:
            next_iter = model.iter_next(selected_iter)
            model.move_after(selected_iter, next_iter)

        tree.scroll_to_cell(model.get_path(selected_iter))

        self.apply()

    def on_toggled(self, cell, path):
        """
            Updates the enabled column
        """
        if self.model[path][4]:
            return

        active = not cell.get_active()
        cell.set_active(active)
        self.model[path][3] = active

        self.apply()

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
            items = u" ".join(items)
        except TypeError:
            items = u""
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
        A class to represent the color button
    """
    def __init__(self, preferences, widget):
        Preference.__init__(self, preferences, widget)

    def _setup_change(self):
        self.widget.connect('color-set', self.change)

    def _set_value(self):
        value = self.preferences.settings.get_option(
            self.name, self.default)

        # Extract alpha value in any case
        if len(value) == 9:
            alpha = int(value[-2:], 16) * 256
            value = value[:-2]

        if self.widget.get_use_alpha():
            self.widget.set_alpha(alpha)

        self.widget.set_color(gtk.gdk.color_parse(value))

    def _get_value(self):
        color = self.widget.get_color()
        value = '#%.2x%.2x%.2x' % (
            color.red / 256,
            color.green / 256,
            color.blue / 256
        )

        if self.widget.get_use_alpha():
            alpha = self.widget.get_alpha()
            value += '%.2x' % (alpha / 256)

        return value

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
        
class FontResetButtonPreference(Button, Conditional):
    '''
        A button to reset a font button to a default font
    '''
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
        self.widget.connect('changed', self.change, self.name,
            self._get_value())

    def _set_value(self):
        """
            Sets the preferences for this widget
        """
        value = self.preferences.settings.get_option(self.name, self.default)
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
                    match_pos, match_pos + len(match[:i]))
                # Insert match at matched position
                self.widget.get_child().insert_text(
                    match, match_pos)
                # Update cursor position
                self.widget.get_child().set_position(match_pos + len(match))

        return True

# vim: et sts=4 sw=4
