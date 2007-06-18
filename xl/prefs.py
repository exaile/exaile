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

import thread, os, os.path, string, shlex
import tracks, xlmisc, media, audioscrobbler, burn
from gettext import gettext as _
import pygtk, common
pygtk.require('2.0')
import gtk, gtk.glade, pango, subprocess

try:
    import gamin
    GAMIN_AVAIL = True
except ImportError:
    GAMIN_AVAIL = False

settings = None
xml = None
TEXT_VIEW_DEFAULT = """<big><b>{title}</b></big>
{artist}
on <i>{album}</i> - [{length}]"""

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
            self.change, self.name, self.widget.get_text())
        self.widget.connect('activate',
            lambda *e: self.change(self.widget, None, self.name,
                self.widget.get_text()))

    def set_pref(self):
        """ 
            Sets the GUI widget up for this preference
        """
        self.widget.set_text(str(settings.get_str(self.name, default=self.default)))

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
        settings.set_str(self.name, self.widget.get_text())
        return True

class CryptedPrefsItem(PrefsItem):
    """
        An encrypted preferences item
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def set_pref(self):
        self.widget.set_text(settings.get_crypted(self.name,
            default=self.default))

    def apply(self):
        if self.done and not self.do_done(): return False
        settings.set_crypted(self.name, self.widget.get_text())
        return True

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
        return buf.get_text(start, end)

    def set_pref(self):
        """
            Sets the value of this widget
        """
        self.widget.get_buffer().set_text(str(settings.get_str(self.name,
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
        settings.set_str(self.name, self.get_all_text())
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
        self.widget.set_active(settings.get_boolean(self.name,
            self.default))

    def apply(self):
        if self.done and not self.do_done(): return False
        settings.set_boolean(self.name, self.widget.get_active())
        return True

class ListPrefsItem(PrefsItem):
    """
        A class to represent a space separated list in the preferences window
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def set_pref(self):
        items = settings.get_list(self.name, default=self.default)
        self.widget.set_text(" ".join(items))

    def apply(self):
        if self.done and not self.do_done(): return False
        text = self.widget.get_text()
        settings.set_list(self.name, shlex.split(text))
        return True

class FloatPrefsItem(PrefsItem):
    """
        A class to represent a floating point number in the preferences window
    """
    def __init__(self, name, default, change=None, done=None):
        PrefsItem.__init__(self, name, default, change, done)

    def set_pref(self):
        self.widget.set_text(str(settings.get_float(self.name, default=self.default)))

    def apply(self):
        if self.done and not self.do_done(): return False
        settings.set_float(self.name, float(self.widget.get_text()))
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
            settings.get_str(self.name, self.default)))

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
        font = settings.get_str(self.name, self.default)
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
        directory = settings.get_str(self.name, self.default)
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
        item = settings.get_str(self.name, self.default)

        if self.use_index:
            index = settings.get_int(self.name, self.default)
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

class Preferences(object):
    """
        Preferences Dialog
    """

    order = (_("General"), _("Advanced"))
    items = ({_("General"):
                (_("Library"),
                _('Notification'),
                _('Last.fm'),
                _('Radio')),
            _("Advanced"):
                '',
            })
    def __init__(self, parent):
        """
            Initilizes the preferences dialog
        """

        global settings, xml

        self.exaile = parent
        self.fields = []
        self.popup = None
        self.osd_settings = xlmisc.get_osd_settings(self.exaile.settings)
        settings = self.exaile.settings
        self.xml = gtk.glade.XML('exaile.glade', 'PreferencesDialog', 'exaile')
        xml = self.xml
        self.window = self.xml.get_widget('PreferencesDialog')
        self.window.set_transient_for(parent.window)
        self.window.connect('delete-event', lambda *e: self.cancel())

        self.nb = self.xml.get_widget('prefs_nb')
        self.nb.set_show_tabs(False)

        self.xml.get_widget('prefs_cancel_button').connect('clicked',
            lambda *e: self.cancel())
        self.xml.get_widget('prefs_apply_button').connect('clicked',
            self.apply)
        self.xml.get_widget('prefs_ok_button').connect('clicked',
            self.ok)

        self.label = self.xml.get_widget('prefs_frame_label')

        self.tree = self.xml.get_widget('prefs_tree')
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Preferences'), text, text=0)
        self.tree.append_column(col)

        self.model = gtk.TreeStore(str, int)
        self.tree.set_model(self.model)

        count = 0
        for header in self.order:
            items = self.items[header]
            node = self.model.append(None, [_(header), count]) # header is a string that must be translated by gettext, therefore it is necessary to wrap it in _() 
            count += 1
            for item in items:
                self.model.append(node, [_(item), _(count)]) # item and count are string that must be translated by gettext, therefore it is necessary to wrap them in _() 
                count += 1
            self.tree.expand_row(self.model.get_path(node), False)

        selection = self.tree.get_selection()
        selection.connect('changed', self.switch_pane)
        selection.select_path((0,))

        xml.get_widget('prefs_lastfm_pass').set_invisible_char('*')
        xml.get_widget('prefs_audio_sink').set_active(0)

        # populate the combobox with available burning programs
        burn_prog_combo = xml.get_widget('prefs_burn_prog')
        burn_progs = burn.check_burn_progs()
        if burn_progs:
            pref = settings.get_str('burn_prog', burn_progs[0])
            for i, prog in enumerate(burn_progs):
                burn_prog_combo.append_text(prog)
                if prog == pref:
                    burn_prog_combo.set_active(i)
        else:
            burn_prog_combo.append_text('No burning programs found')
            burn_prog_combo.set_active(0)
            burn_prog_combo.set_sensitive(False)
           
        self.text_display = PrefsTextViewItem('osd/display_text',
            TEXT_VIEW_DEFAULT, self.display_popup)
        self.fields.append(self.text_display)
        self.fields.append(ComboPrefsItem('ui/tab_placement',
            0, None, self.setup_tabs, use_index=True))

        simple_settings = ({
            'ui/use_splash': (CheckPrefsItem, True),
#            'watch_directories': (CheckPrefsItem, False, self.check_gamin,
#                self.setup_gamin),
#            'watch_exclude_dirs': (ListPrefsItem, []),
            'fetch_covers': (CheckPrefsItem, True),
            'save_queue': (CheckPrefsItem, True),
            'ui/ensure_visible': (CheckPrefsItem, True),
            'art_filenames': (ListPrefsItem, 
                ['cover.jpg', 'folder.jpg', '.folder.jpg', 'album.jpg', 'art.jpg']),
            'open_last': (CheckPrefsItem, True),
            'osd/enabled': (CheckPrefsItem, True),
            'osd/w': (PrefsItem, '400', self.osd_adjust_size),
            'osd/h': (PrefsItem, '95', self.osd_adjust_size),
            'lastfm/user': (PrefsItem, ''),
            'lastfm/pass': (CryptedPrefsItem, '', None, self.setup_lastfm),
            'cd_device': (PrefsItem, '/dev/cdrom'),
            'audio_sink': (ComboPrefsItem, 'Use GConf Settings'),
            'burn_prog': (ComboPrefsItem, (burn_progs and burn_progs[0]) or ''),
            'osd/tray': (CheckPrefsItem, True),
            'osd/bgcolor': (ColorButtonPrefsItem, '#567ea2',
                self.osd_colorpicker),
            'osd/text_color': (ColorButtonPrefsItem, '#ffffff',
                self.osd_colorpicker),
            'osd/text_font': (FontButtonPrefsItem, 'Sans 10',
                self.osd_fontpicker),
            'ui/use_tray': (CheckPrefsItem, False, None, self.setup_tray),
            'amazon_locale': (ComboPrefsItem, 'us'),
            'wikipedia_locale': (PrefsItem, 'en'),
            'scan_interval': (FloatPrefsItem, 25, None,
                self.setup_scan_interval),
            'download_feeds': (CheckPrefsItem, True),
            'ui/use_alphabet': (CheckPrefsItem, True),
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

    def setup_scan_interval(self, widget):
        """
            Makes sure the scan interval is valid, and starts it over with the
            new time value
        """
        value = widget.get_text()

        try:    
            value = float(value)

            if value < 1 and value != 0:
                common.error(self.exaile.window, "Library scan interval must "
                    "be at least 1 minute.")
                return False
        except ValueError:  
            common.error(self.exaile.window, "%s is an invalid value "
                "for the library rescan interval" % value)
            return False

        self.exaile.start_scan_interval(value)
        return True

    def check_gamin(self, widget):
        """
            Make sure gamin is availabe
        """
        if widget.get_active():
            if not GAMIN_AVAIL:
                common.error(self.exaile.window,
                    _("Cannot watch directories for changes. "
                    "Install python2.4-gamin to use this feature."))
                widget.set_active(False)
                return False

    def setup_lastfm(self, widget):
        """
            Connects to last.fm if the password field isn't empty
        """
        if not widget.get_text(): return True
        user = xml.get_widget('prefs_lastfm_user').get_text()
        password = widget.get_text()

        thread.start_new_thread(audioscrobbler.get_scrobbler_session,
            (self.exaile, user, password, True))
        return True

    def setup_gamin(self, widget):
        """
            Sets up gamin if needs be
        """
        if widget.get_active() and not self.exaile.mon:
            self.exaile.setup_gamin(True)
        return True

    def setup_tabs(self, widget, *p):
        """
            Sets up tab placement for the playlists tab
        """

        index = widget.get_active()
        self.exaile.set_tab_placement(index)
        return True

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

        xlmisc.POPUP = None

        return True

    def setup_tray(self, widget, event=None):
        """
            Sets up the tray icon
        """
        val = widget.get_active()

        if val: self.exaile.setup_tray()
        else: self.exaile.remove_tray()
        return True

    def osd_adjust_size(self, widget, event, name, previous):
        """
            Called when the user requests to adjust the size of the osd
        """

        try:
            val = int(widget.get_text())
        except ValueError:
            widget.set_text(previous)
            return
        
        self.osd_settings[name] = val
        self.display_popup()

    def osd_fontpicker(self, widget, name):
        """
            Gets the font from the font picker, and re-sets up the OSD window
        """

        self.osd_settings[name] = widget.get_font_name()
        self.display_popup()

    def osd_colorpicker(self, widget, name):
        """
            Shows a colorpicker
        """
        color = widget.get_color()
        string = "#%.2x%.2x%.2x" % (color.red / 257, color.green / 257, 
            color.blue / 257)

        self.osd_settings[name] = string
        self.display_popup()

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
            common.escape_xml(title.get_label()))
        if index == 2: 
            self.osd_settings = xlmisc.get_osd_settings(self.exaile.settings)
            self.display_popup()
        else:
            if self.popup:
                self.popup.window.destroy()
                self.popup = None

    def display_popup(self, *e):
        """
            Shows the OSD window
        """
        if self.popup:  
            (x, y) = self.popup.window.get_position()
            self.osd_settings['osd/x'] = x
            self.osd_settings['osd/y'] = y
            self.popup.window.destroy()

        self.popup = xlmisc.OSDWindow(self.exaile, self.osd_settings,
            False, True)

        track = BlankClass() 
        for item in ('title', 'artist', 'album', 'length', 'track', 'bitrate',
            'genre', 'year', 'rating'):
            setattr(track, item, item)

        display_text = self.text_display.get_all_text()
        display_text = display_text.replace("{volume}", "\\{volume\\}")

        self.popup.show_track_osd(track, display_text, 
            'images%snocover.png' % os.sep)       

        return False

    def run(self):
        """
            Runs the dialog
        """
        self.window.show_all()

class BlankClass(object):
    pass
