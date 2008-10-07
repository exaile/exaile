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

import thread, os, shlex, string, urllib2
from gettext import gettext as _
import pygtk
pygtk.require('2.0')
import gtk, gtk.glade
from xl import xdg

settings = None

class PrefsItem(object):
    """
        Representing a gtk.Entry preferences item
    """
    def __init__(self, name, default, change=None, done=None):
        """
            Initializes the preferences item
            expects the name of the widget in the .glade file, the default for
            this setting, an optional function to be called when the value is
            changed, and an optional function to be called when this setting
            is applied
        """

        self.widget = xml.get_widget(('prefs_%s' % name).replace("/", "_"))
        self.name = name
        self.default = default
        self.change = change
        self.done = done

        self.set_pref()
        if change: 
            self.setup_change()

    def setup_change(self):
        """
            Sets up the function to be called when this preference is changed
        """
        self.widget.connect('focus-out-event',
            self.change, self.name, unicode(self.widget.get_text(), 'utf-8'))
        self.widget.connect('activate',
            lambda *e: self.change(self.widget, None, self.name,
                unicode(self.widget.get_text(), 'utf-8')))

    def set_pref(self):
        """ 
            Sets the GUI widget up for this preference
        """
        if not self.widget:
            xlmisc.log("Widget not found: %s" % (self.name))
            return
        self.widget.set_text(str(settings.get_option(self.name, default=self.default)))

    def do_done(self):
        """
            Calls the done function
        """
        return self.done(self.widget)

    def apply(self):
        """
            applies this setting
        """
        if self.done and not self.do_done(): return False
        settings[self.name] = unicode(self.widget.get_text(), 'utf-8')
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
       
class CheckPrefsItem(PrefsItem):
    """
        A class to represent check boxes in the preferences window
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def setup_change(self):
        self.widget.connect('toggled',
            self.change)

    def set_pref(self):
        self.widget.set_active(settings.get_option(self.name,
            self.default))

    def apply(self):
        if self.done and not self.do_done(): return False
        settings[self.name] = self.widget.get_active()
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

class PreferencesDialog(object):
    """
        Preferences Dialog
    """

    CATEGORIES = [
        # TRANSLATORS: Category of the preferences dialog
        (_("General"), [
            # TRANSLATORS: Category of the preferences dialog
            _("Library"),
        ]),
        # TRANSLATORS: Category of the preferences dialog
        (_("Advanced"), [
            _("After"),
        ]),
    ]

    def __init__(self, parent, main):
        """
            Initilizes the preferences dialog
        """

        global settings, xml

        self.main = main
        self.parent = parent
        settings = self.main.exaile.settings
        self.popup = None
        self.xml = gtk.glade.XML(xdg.get_data_path('glade/preferences_dialog.glade'), 
            'PreferencesDialog', 'exaile')
        xml = self.xml
        self.window = self.xml.get_widget('PreferencesDialog')
        self.window.set_transient_for(parent)
        self.window.connect('delete-event', lambda *e: self.cancel())
#        self.xml.get_widget('show_advanced_button').connect('clicked',
#            lambda *e: advancededitor.AdvancedConfigEditor(self.exaile,
#            self.window, self, settings, 'data/settings_meta.ini'))

        self.nb = self.xml.get_widget('prefs_nb')
        self.nb.set_show_tabs(False)

        self._connect_events()

        self.label = self.xml.get_widget('prefs_frame_label')

        self.tree = self.xml.get_widget('prefs_tree')
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Preferences'), text, text=0)
        self.tree.append_column(col)

        self.model = gtk.TreeStore(str, int)
        self.tree.set_model(self.model)
        count = 0
        for cat, subcats in self.CATEGORIES:
            catnode = self.model.append(None, [cat, count])
            count += 1
            for subcat in subcats:
                self.model.append(catnode, [subcat, count])
                count += 1
            self.tree.expand_row(self.model.get_path(catnode), False)

        selection = self.tree.get_selection()
        selection.connect('changed', self.switch_pane)
        selection.select_path((0,))

        self.setup_settings()

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.xml.signal_autoconnect({
            'on_cancel_button_clicked': lambda *e: self.cancel(),
            'on_apply_button_clicked': self.apply,
            'on_ok_button_clicked': self.ok,
        })

    def setup_settings(self):
        """
            Sets the various widgets and settings preferences
        """
        global settings

        self.fields = []

        simple_settings = ({
            'gui/use_splash': (CheckPrefsItem, True),
        })

        for setting, value in simple_settings.iteritems():
            c = value[0]
            default = value[1]
            if len(value) == 3: change = value[2]
            else: change = None

            if len(value) == 4: done = value[3]
            else: done = None
            item = c(setting, default, change, done)
            self.fields.append(item)

    setting_changed = setup_settings

    def ok(self, widget):
        """
            Called when the user clicks 'ok'
        """
        if self.apply(None): 
            self.cancel()
            self.window.hide()
            self.window.destroy()

    def apply(self, widget):
        """
            Applies settings
        """
        for item in self.fields:
            if not item.apply():
                print item.name
                return False

        return True

    def cancel(self):
        """
            Closes the preferences dialog, ensuring that the osd popup isn't
            still showing
        """
        if self.popup:
            self.popup.window.hide()
            self.popup.window.destroy()
        self.window.hide()
        self.window.destroy()

    def switch_pane(self, selection):
        """
            Switches a pane
        """
        (model, iter) = selection.get_selected()
        if not iter: return
        index = self.model.get_value(iter, 1)
        self.nb.set_current_page(index)
        page = self.nb.get_nth_page(index)
        title = self.nb.get_tab_label(page)
        self.label.set_markup("<b>%s</b>" %
            title.get_label())
 
    def run(self):
        """
            Runs the dialog
        """
        self.window.show_all()

class BlankClass(object):
    pass
