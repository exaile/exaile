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
import os.path
import sys
import webbrowser

from urllib import pathname2url

from gi.repository import Gtk
from gi.repository import Pango

from xl.common import enum
from xl.nls import gettext as _
from xlgui.preferences import widgets

import _widgets

from _base import BASE_DIR, PLUGIN_INFO, SETTINGS, get_path
from _database import FileChooserDialog
from _utils import get_icon


# Needed by definition (see __init__.Plugin.get_preferences_pane)
#: Name of plugin
name = PLUGIN_INFO.name

# Needed by definition (see __init__.Plugin.get_preferences_pane)
#: str: Path to ui file
ui = get_path('preferences.ui')

#: IconSizePreference: Global reference to IconSizePreference (needed to link)
_icon_size_preference = None

#: IconsPreference: Global reference to IconsPreference (needed to link)
_icon_preference = None


def _get_icon_size():
    """
        Gets icon size
        :return: int
    """
    return _icon_size_preference.value if _icon_size_preference else SETTINGS['icon_size']


def _link_icons_widgets():
    """
        Try to link _icon_size_preference and _icon_preference
        :return: None
    """
    if _icon_size_preference and _icon_preference:
        _icon_size_preference.widget.connect('value-changed', _icon_preference.on_icon_size_changed)


def _create_base_class(s_name, base_class=widgets.Preference):
    """
        Creates the base class
        :param s_name: str - setting name  (e.g. 'database')
        :param base_class: widgets.Preference
        :return: type
    """
    def apply(self):
        """
            Applies change
            :param self:
            :return: None
        """
        SETTINGS[self.S_NAME] = self._get_value()

    @property
    def builder(self):
        """
            Gets the builder to preferences
            :param self: widgets.Preference
            :return: Gtk.Builder
        """
        return self.preferences.builders[
                sys.modules[__name__]
            ]

    obj = {
        'S_NAME': s_name,
        'apply': apply,
        'builder': builder,
        'default': SETTINGS.DEFAULTS.get(s_name, lambda: '')(),
        'name': '/'.join(['plugin', PLUGIN_INFO.id, s_name]),
        'value': property(lambda self: self._get_value())
    }

    return type('_%sPreferenceBase' % s_name.capitalize(), (base_class,), obj)


def _create_on_off_value_preference(s_name):
    """
        Creates class to on/off preferences
        :param s_name: setting name
        :return: a new type
    """
    SWITCH_NAME = s_name + '_switch'

    @property
    def switch_widget(self):
        """
            On/Off widget
            :param self: widgets.Preference
            :return: Gtk.Switch
        """
        widgets = getattr(self, 'widgets', None)
        if widgets is None:
            widgets = self.widgets = _widgets.Widgets(
            self.builder, SWITCH_NAME,
            **{SWITCH_NAME: self.on_state_set}
        )

        return widgets[SWITCH_NAME]

    # Called by super
    def _get_value(self):
        """
            Get the value
            :param self: widgets.Preference
            :return: int
        """
        if self.switch_widget.get_active():
            return self.widget.get_value()
        else:
            return 0

    # Called by super
    def _set_value(self):
        """
            Set the value from option on widget
            :param self: widgets.Preference
            :return: None
        """
        value = SETTINGS[self.S_NAME]
        active = (value > 0)
        if not active:
            value = SETTINGS.DEFAULTS[self.S_NAME]()

        self.widget.set_value(value)
        self.widget.set_sensitive(active)

        self.switch_widget.set_active(active)

    # Called by super
    def _setup_change(self):
        _widgets.connect(self.widget, ['value-changed'], self.change)

    def on_state_set(self, _switch, state):
        """
            On state set
            :param self: widgets.Preference
            :param _switch: Gtk.Switch
            :param state: bool
            :return: None
        """
        self.widget.set_sensitive(state)
        self.widget.grab_focus()
        self.widget.set_position(-1)
        self.change()

    base_class = _create_base_class(s_name)
    obj = {
        'switch_widget': switch_widget,
        '_get_value': _get_value,
        '_set_value': _set_value,
        '_setup_change': _setup_change,
        'on_state_set': on_state_set
    }

    return type('%sPreference' % s_name.capitalize(), (base_class,), obj)


#: ExpandPreference: Class to handle 'expand' preference
ExpandPreference = _create_on_off_value_preference('expand')

#: MonitorPreference: Class to handle 'monitor' preference
MonitorPreference = _create_on_off_value_preference('monitor')


class DatabasePreference(_create_base_class('database')):
    """
        Class that handles 'database' preference
    """
    def __init__(self, preferences, widget):
        """
            Constructor
            Connect to events on 'database_button' object
            :param preferences: xlgui.preferences.PreferencesDialog
            :param widget: Gtk.Widget
        """
        super(DatabasePreference, self).__init__(
            preferences, widget
        )

        self.widgets = _widgets.Widgets(
            self.builder,
            ['file_button'],
            file_button=FileChooserDialog(
                preferences.window,
                self.__on_database_config_change)
        )


    # Called by super
    def _get_value(self):
        """
            Get the value
            :return: str
        """
        return str(self.widget.get_text())

    # Called by super
    def _set_value(self):
        """
            Set the value from option on widget
            :return: None
        """
        self.widget.set_text(SETTINGS[self.S_NAME])

    def __on_database_config_change(self):
        """
            On database config change
            :return: None
        """
        self._set_value()
        self.widget.grab_focus()


class DrawSeparatorsPreference(
    _create_base_class('draw_separators', widgets.CheckPreference)
):
    """
        Class that handles 'draw_separators' preference
    """


class FontPreference(
    _create_base_class('font', widgets.FontButtonPreference)
):
    """
        Class that handles 'font' preference
    """


class IconsPreference(_create_base_class('icons')):
    """
        Class that handles 'icons' preference
    """
    def __init__(self, preferences, widget):
        """
            Constructor
            :param preferences:
            :param widget:
        """
        super(IconsPreference, self).__init__(preferences, widget)

        cr = Gtk.CellRendererPixbuf()
        col = Gtk.TreeViewColumn('', cr, pixbuf=0)

        self.widget.append_column(col)

        cr = Gtk.CellRendererText()
        cr.connect('edited', self.__on_text_edited, 1)
        cr.set_property('editable', True)
        col = Gtk.TreeViewColumn(_('Field name'), cr, text=1)
        self.widget.append_column(col)

        cr = Gtk.CellRendererText()
        cr.connect('edited', self.__on_text_edited, 2)
        cr.set_property('editable', True)
        col = Gtk.TreeViewColumn(_('Icon name'), cr, text=2)

        self.widget.append_column(col)

        #self.icons_model = self.widgets['icons_model']

        global _icon_preference
        _icon_preference = self
        _link_icons_widgets()

    @property
    def icons_model(self):
        """
            Get icons model
            :return: Gtk.TreeModel
        """
        widgets = getattr(self, 'widgets', None)
        if widgets is None:
            widgets = self.widgets = _widgets.Widgets(self.builder, ['icons_model'])

        return widgets['icons_model']

    def on_icon_size_changed(self, *_params):
        """
            On icon size value changed, resize it
            :param _params: ignored
            :return: None
            :see: Gtk.ScaleButton.signals.value_changed
        """
        self._set_value()

    def __on_text_edited(self, _cr, path, new_text, column):
        """
            On text edited
            :param _cr: Gtk.CellRenderer
            :param path: str
            :param new_text: str
            :param column: int
            :return: None
        """
        icons_model = self.icons_model
        it = icons_model.get_iter(path)
        icons_model.set_value(it, column, new_text)

        if column == 1 and new_text and icons_model.iter_next(it) is None:
            icons_model.append([None, '', ''])

        if column == 2:
            icons_model.set_value(it, 0, get_icon(new_text, _get_icon_size()))

    # Called by super
    def _set_value(self):
        """
            Set the value from option on widget
            :return: None
        """
        icons_model = self.icons_model
        icons_model.clear()
        icons_settings = SETTINGS[self.S_NAME]
        for key, value in sorted(icons_settings.items()):
            icons_model.append([
                get_icon(value, _get_icon_size()), key, value
            ])

        icons_model.append([None, '', ''])

    # Called by super
    def _get_value(self):
        """
            Get the value
            :return: dict
        """
        result = {}
        icons_model = self.icons_model
        it = icons_model.get_iter_first()
        while it:
            field_name = icons_model.get_value(it, 1)
            if field_name:
                result[field_name] = icons_model.get_value(it, 2)

            it = icons_model.iter_next(it)

        return result if result else self.default


class IconSizePreference(
    _create_base_class('icon_size', widgets.ScalePreference)
):
    """
        Class that handles 'icon_size' preference
    """
    def __init__(self, preferences, widget):
        """
            Constructor
            :param preferences: xlgui.preferences.PreferencesDialog
            :param widget: Gtk.Widget
        """
        super(IconSizePreference, self).__init__(
            preferences, widget
        )

        for val in [16, 24, 32, 48]:
            widget.add_mark(val, Gtk.PositionType.BOTTOM, str(val))

        global _icon_size_preference
        _icon_size_preference = self
        _link_icons_widgets()

    # Called by super
    def _setup_change(self):
        """
            Connect events
            :return: None
        """
        widget = self.widget
        _widgets.connect(
            widget, ['focus-out-event'], self.change
        )
        _widgets.connect(
            widget, ['change-value'], lambda *_: widget.grab_focus()
        )
        _widgets.connect(
            widget, ['format-value'],
            lambda _gtk_scale, value: str(int(value)) + ' ' + _('px')
        )

    # Called by super
    def _get_value(self):
        """
            Get value for preference
            :return: int
        """
        return int(super(IconSizePreference, self)._get_value())


class PatternsPreference(
    _create_base_class(
        'patterns', widgets.TextViewPreference
    )
):
    """
        Class that handles 'patterns' preference
        This is handled as a list of strings
    """
    TagClasses = enum(General=0, Name=1, Operator=2, Escape=3)

    def __init__(self, preferences, widget):
        """
            Constructor
            :param preferences:
            :param widget:
        """
        # Define needed data before calling super.__init__
        self.text_buffer = text_buffer = widget.get_buffer()

        # Define tag classes
        tag_classes = self.TagClasses
        self._TAGS = {
            tag_classes.General:
                text_buffer.create_tag(None, foreground="Black"),
            tag_classes.Name:
                text_buffer.create_tag(None, foreground="Green"),
            tag_classes.Operator:
                text_buffer.create_tag(None, foreground="Red"),
            tag_classes.Escape:
                text_buffer.create_tag(None, foreground="Black",
                                       weight=Pango.Weight.BOLD)
        }

        # super.__init__
        super(PatternsPreference, self).__init__(
            preferences, widget
        )

        self.widgets = _widgets.Widgets(self.builder, ['help_button'],
                                        help_button=self.__on_clicked)

        # Connect signals
        text_buffer.connect('changed', self.__on_pattern_textbuffer_changed)

    def __on_clicked(self, *_args):
        """
            Opens readme
            :param _args: ignored
            :return: None
        """
        uri = 'file:' + pathname2url(os.path.join(BASE_DIR, 'README.html'))
        webbrowser.open(uri)

    def __apply_tags(self):
        """
            Apply tags to Gtk.TextBuffer (syntax coloring)
            :return: None
        """
        tags = self._TAGS
        text_buffer = self.text_buffer
        text_buffer.remove_all_tags(
            text_buffer.get_start_iter(), text_buffer.get_end_iter()
        )
        cur_it = text_buffer.get_start_iter()

        on_name = False
        has_ended = False
        while not has_ended:
            tag_class = self.TagClasses.General
            count = 1
            cur_char = cur_it.get_char()
            if cur_char in ['\n', '\r', '\t']:
                has_ended = not cur_it.forward_chars(count)
            else:
                if cur_char in ['(', '[']:
                    on_name = True
                elif cur_char in [')', ']']:
                    on_name = False
                elif on_name:
                    if cur_char == ':':
                        tag_class = self.TagClasses.Operator
                        on_name = False
                    elif cur_char in ['?', '!', '*', '>']:
                        tag_class = self.TagClasses.Operator
                    else:
                        tag_class = self.TagClasses.Name
                elif cur_char == '\\':
                    tag_class = self.TagClasses.Escape
                    count = 2
                elif cur_char in ['%', '&']:
                    tag_class = self.TagClasses.Operator

                start_it = cur_it.copy()
                has_ended = not cur_it.forward_chars(count)
                end_it = text_buffer.get_end_iter() if has_ended else cur_it
                text_buffer.apply_tag(tags[tag_class], start_it, end_it)

    def __on_pattern_textbuffer_changed(self, textbuffer):
        """
            On pattern textbuffer changed
            :param textbuffer: Gtk.TextBuffer
            :return: None
        """
        value = self.get_all_text()
        if value == '':
            # Restore default
            value = SETTINGS.DEFAULTS[self.S_NAME]()
            textbuffer.set_text('\n'.join(value))
        else:
            self.__apply_tags()

    # Called by super
    def _get_value(self):
        """
            Get the value
            :return: [str] - list of strings
        """
        value = self.get_all_text()
        return (
            SETTINGS.DEFAULTS[self.S_NAME]() if value == ''
            else value.split('\n')
        )

    # Called by super
    def _set_value(self):
        """
            Set the value from option on widget
            :return: None
        """
        value = SETTINGS[self.S_NAME]

        text_buffer = self.widget.get_buffer()
        text_buffer.set_text('\n'.join(value))
        self.__apply_tags()
