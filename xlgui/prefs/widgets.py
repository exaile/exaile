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

        if hasattr(self, 'change'):
            self._setup_change()

        self._set_pref()

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

    def apply(self):
        """
            applies this setting
        """
        if hasattr(self, 'done') and not self.done(): return False
        self.prefs.settings[self._get_name()] = \
            unicode(self.widget.get_text(), 'utf-8')
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

    def apply(self):
        if hasattr(self, 'done') and not self.done(): return False
        self.prefs.settings[self._get_name()] = self.widget.get_active()
        return True

#class CryptedPrefsItem(PrefsItem):
#    """
#        An encrypted preferences item
#    """
#    def __init__(self, name, default, change=None, done=None):
#        PrefsItem.__init__(self, name, default, change, done)

#    def set_pref(self):
#        self.widget.set_text(settings.get_crypted(self.name,
#            default=self.default))

#    def apply(self):
#        if self.done and not self.do_done(): return False
#        settings.set_crypted(self.name, unicode(self.widget.get_text(), 'utf-8'))
#        return True

class PrefsTextViewItem(PrefsItem):
    """
        Represents a gtk.TextView
    """
    def __init__(self, name, default, change=None, done=None):
        """
            Initializes the object
        """
        PrefsItem.__init__(self, name, default, change, done)

    def setup_change(self):
        """
            Detects changes in this widget
        """
        self.widget.connect('focus-out-event',
            self.change, self.name, self.get_all_text())

    def get_all_text(self):
        """
            Returns the value of the text buffer
        """
        buf = self.widget.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return unicode(buf.get_text(start, end), 'utf-8')

    def set_pref(self):
        """
            Sets the value of this widget
        """
        self.widget.get_buffer().set_text(str(settings.get_option(self.name,
            default=self.default)))

    def do_done(self):
        """
            Calls the done function
        """
        return self.done(self.widget)

    def apply(self):    
        """
            Applies the setting
        """
        if self.done and not self.do_done(): return False
        settings['self.name'] = self.get_all_text()
        return True
       


class ListPrefsItem(PrefsItem):
    """
        A class to represent a space separated list in the preferences window
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def set_pref(self):
        items = settings.get_option(self.name, default=self.default)
        try:
            items = " ".join(items)
        except:
            items = ""
        self.widget.set_text(items)

    def apply(self):
        if self.done and not self.do_done(): return False
        # shlex is broken with unicode, so we feed it UTF-8 and encode
        # afterwards.
        values = shlex.split(self.widget.get_text())
        values = [unicode(value, 'utf-8') for value in values]
        settings[self.name] = values
        return True

class SpinPrefsItem(PrefsItem):
    def set_pref(self):
        value = settings.get_option(self.name, default=self.default)
        self.widget.set_value(value)

class FloatPrefsItem(PrefsItem):
    """
        A class to represent a floating point number in the preferences window
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def set_pref(self):
        self.widget.set_text(str(settings.get_option(self.name, default=self.default)))

    def apply(self):
        if self.done and not self.do_done(): return False
        settings[self.name] = float(self.widget.get_text())
        return True

class ColorButtonPrefsItem(PrefsItem):
    """
        A class to represent the color button in the prefs window
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def setup_change(self):
        self.widget.connect('color-set',
            self.change, self.name)

    def set_pref(self):
        self.widget.set_color(gtk.gdk.color_parse(
            settings.get_option(self.name, self.default)))

    def apply(self):
        if self.done and not self.do_done(): return False
        color = self.widget.get_color()
        string = "#%.2x%.2x%.2x" % (color.red / 257, color.green / 257, 
            color.blue / 257)
        settings[self.name] = string
        return True

class FontButtonPrefsItem(ColorButtonPrefsItem):
    """
        Font button
    """
    def __init__(self, name, default, change=None, done=None):
        ColorButtonPrefsItem.__init__(self, name, default, change, done)

    def setup_change(self):
        self.widget.connect('font-set', self.change, self.name)

    def set_pref(self):
        font = settings.get_option(self.name, self.default)
        self.widget.set_font_name(font)
        
    def apply(self):
        if self.done and not self.do_don(): return False
        font = self.widget.get_font_name()
        settings[self.name] = font
        return True

class DirPrefsItem(PrefsItem):
    """
        Directory chooser button
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def setup_change(self):
        pass

    def set_pref(self):
        """
            Sets the current directory
        """
        directory = os.path.expanduser(settings.get_option(self.name, self.default))
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.widget.set_filename(directory)

    def apply(self):
        if self.done and not self.do_done(): return False
        directory = self.widget.get_filename()
        settings[self.name] = directory
        return True

class ComboPrefsItem(PrefsItem):
    """
        combo box
    """
    def __init__(self, name, default, change=None, done=None, 
        use_index=False):
        self.use_index = use_index
        PrefsItem.__init__(self, name, default, change, done)

    def setup_change(self):
        self.widget.connect('changed',
            self.change)

    def set_pref(self):
        item = settings.get_option(self.name, self.default)

        if self.use_index:
            index = settings.get_option(self.name, self.default)
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

    def apply(self):
        if self.done and not self.do_done(): return False

        if self.use_index:
            settings[self.name] = self.widget.get_active()
        else:
            settings[self.name] = self.widget.get_active_text()
        return True
