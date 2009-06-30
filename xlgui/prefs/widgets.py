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

import os, gtk.gdk

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

        self._set_pref()
        if hasattr(self, 'change'):
            self._setup_change()

    def _get_name(self):
        return self.name

    def _setup_change(self):
        """
            Sets up the function to be called when this preference is changed
        """
        self.widget.connect('focus-out-event',
            self.change, self._get_name(), unicode(self.widget.get_text(), 'utf-8'))
        self.widget.connect('activate',
            lambda *e: self.change(self.widget, None, self._get_name(),
                unicode(self.widget.get_text(), 'utf-8')))

    def _set_pref(self):
        """ 
            Sets the GUI widget up for this preference
        """
        if not self.widget:
            xlmisc.log("Widget not found: %s" % (self.name))
            return
        self.widget.set_text(str(self.prefs.settings.get_option(
            self._get_name(), self.default)))

    def _settings_value(self):
        """
            Value to be stored into the settings file
        """
        return unicode(self.widget.get_text(), 'utf-8')

    def apply(self, value=None):
        """
            applies this setting
        """
        if hasattr(self, 'done') and not self.done(): return False
        if value is None:
            value = self._settings_value()
        self.prefs.settings.set_option(self._get_name(), value)
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

    def _set_pref(self):
        self.widget.set_active(
            self.prefs.settings.get_option(self._get_name(),
            self.default))

    def _settings_value(self):
        return self.widget.get_active()


class DirPrefsItem(PrefsItem):
    """
        Directory chooser button
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        pass

    def _set_pref(self):
        """
            Sets the current directory
        """
        directory = os.path.expanduser(
            self.prefs.settings.get_option(self._get_name(), self.default))
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.widget.set_filename(directory)

    def _settings_value(self):
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

    def _set_pref(self):
        """
            Sets the preferences for this widget
        """
        items = self.prefs.settings.get_option(self._get_name(),
            self.default)

        self.model.clear()
        for item in items:
            self.model.append([item])

    def _settings_value(self):
        items = []
        iter = self.model.get_iter_first()
        while iter:
            items.append(self.model.get_value(iter, 0))
            iter = self.model.iter_next(iter)
        self.items = items
        return items


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

    def _set_pref(self):
        """
            Sets the value of this widget
        """
        self.widget.get_buffer().set_text(str(
            self.prefs.settings.get_option(self._get_name(),
            default=self.default)))

    def _settings_value(self):    
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

    def _set_pref(self):
        items = self.prefs.settings.get_option(self._get_name(), 
            default=self.default)
        try:
            items = " ".join(items)
        except:
            items = ""
        self.widget.set_text(items)

    def _settings_value(self):
        # shlex is broken with unicode, so we feed it UTF-8 and encode
        # afterwards.
        values = shlex.split(self.widget.get_text())
        values = [unicode(value, 'utf-8') for value in values]
        return values


class SpinPrefsItem(PrefsItem):
    def _set_pref(self):
        value = self.prefs.settings.get_option(self._get_name(), 
            default=self.default)
        self.widget.set_value(value)

    def _setup_change(self):
        self.widget.connect('value-changed', self.change)

    def _settings_value(self):
        return self.widget.get_value()


class FloatPrefsItem(PrefsItem):
    """
        A class to represent a floating point number in the preferences window
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _set_pref(self):
        self.widget.set_text(str(
            self.prefs.settings.get_option(self._get_name(), 
            default=self.default)))

    def _settings_value(self):
        return float(self.widget.get_text())


class IntPrefsItem(FloatPrefsItem):

    def _settings_value(self):
        return int(self.widget.get_text())


class ColorButtonPrefsItem(PrefsItem):
    """
        A class to represent the color button in the prefs window
    """
    def __init__(self, prefs, widget):
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('color-set', self.change)

    def _set_pref(self):
        self.widget.set_color(gtk.gdk.color_parse(
            self.prefs.settings.get_option(self._get_name(), 
            self.default)))

    def _settings_value(self):
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

    def _set_pref(self):
        font = self.prefs.settings.get_option(self._get_name(), 
            self.default)
        self.widget.set_font_name(font)
        
    def _settings_value(self):
        font = self.widget.get_font_name()
        return font


class ComboPrefsItem(PrefsItem):
    """
        combo box
    """
    def __init__(self, prefs, widget, use_index=False, use_map=False):
        self.use_index = use_index
        self.use_map = use_map
        PrefsItem.__init__(self, prefs, widget)

    def _setup_change(self):
        self.widget.connect('changed', self.change)

    def _set_pref(self):
        item = self.prefs.settings.get_option(self._get_name(), 
            self.default)

        if self.use_map:
            index = self.map.index(self.prefs.settings.get_option(
                        self._get_name(), self.default))
            self.widget.set_active(index)
            return

        if self.use_index:
            index = self.prefs.settings.get_option(self._get_name(), 
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

    def _settings_value(self):
        if self.use_map:
            return self.map[self.widget.get_active()]
        elif self.use_index:
            return self.widget.get_active()
        else:
            return self.widget.get_active_text()
