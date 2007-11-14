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

import thread, os, shlex, string
from gettext import gettext as _
import pygtk, common
pygtk.require('2.0')
import gtk, gtk.glade
import cd_import, xlmisc, audioscrobbler, burn, advancededitor
import xl.path

#try:
#    import gamin
#    GAMIN_AVAIL = True
#except ImportError:
#    GAMIN_AVAIL = False
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
            self.change, self.name, unicode(self.widget.get_text(), 'utf-8'))
        self.widget.connect('activate',
            lambda *e: self.change(self.widget, None, self.name,
                unicode(self.widget.get_text(), 'utf-8')))

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
        settings.set_str(self.name, unicode(self.widget.get_text(), 'utf-8'))
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
        settings.set_crypted(self.name, unicode(self.widget.get_text(), 'utf-8'))
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
        return unicode(buf.get_text(start, end), 'utf-8')

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
        settings.set_list(self.name, values)
        return True

class SpinPrefsItem(PrefsItem):
    def set_pref(self):
        value = settings.get_float(self.name, default=self.default)
        self.widget.set_value(value)

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

    CATEGORIES = [
        # TRANSLATORS: Category of the preferences dialog
        (_("General"), [
            # TRANSLATORS: Category of the preferences dialog
            _("Library"),
            # TRANSLATORS: Category of the preferences dialog
            _("Notification"),
            # TRANSLATORS: Category of the preferences dialog
            _("Importing"),
            # TRANSLATORS: Category of the preferences dialog
            _("Last.fm"),
            # TRANSLATORS: Category of the preferences dialog
            _("Radio"),
        ]),
        # TRANSLATORS: Category of the preferences dialog
        (_("Advanced"), [
            _("Replay Gain"),
            # TRANSLATORS: Category of the preferences dialog
            _("Proxy Settings")
        ]),
    ]

    def __init__(self, parent):
        """
            Initilizes the preferences dialog
        """

        global settings, xml

        self.exaile = parent
        settings = self.exaile.settings
        self.popup = None
        self.xml = gtk.glade.XML('exaile.glade', 'PreferencesDialog', 'exaile')
        xml = self.xml
        self.window = self.xml.get_widget('PreferencesDialog')
        self.window.set_transient_for(parent.window)
        self.window.connect('delete-event', lambda *e: self.cancel())
        self.xml.get_widget('show_advanced_button').connect('clicked',
            lambda *e: advancededitor.AdvancedConfigEditor(self.exaile,
            self.window, self, settings, 'data/settings_meta.ini'))

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

        xml.get_widget('prefs_lastfm_pass').set_invisible_char('*')
        xml.get_widget('prefs_audio_sink').set_active(0)


        self.setup_settings()

    def setup_settings(self):
        """
            Sets the various widgets and settings preferences
        """
        global settings
        
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
            burn_prog_combo.append_text(_('No burning programs found'))
            burn_prog_combo.set_active(0)
            burn_prog_combo.set_sensitive(False)

        self.fields = []
        self.osd_settings = xlmisc.get_osd_settings(self.exaile.settings)
           
        # populate the import format combobox
        import_format = xml.get_widget('prefs_import_format')
        import_formats = cd_import.check_import_formats()
        if import_formats:
            pref = settings.get_str('import_format', import_formats[0])
            for i, format in enumerate(import_formats):
                import_format.append_text(format)
                if format == pref:
                    import_format.set_active(i)
        else:
            import_format.append_text(_('No suitable GStreamer plugins found'))
            import_format.set_active(0)
            import_format.set_sensitive(False)

        self.text_display = PrefsTextViewItem('osd/display_text',
            TEXT_VIEW_DEFAULT, self.display_popup)
        self.fields.append(self.text_display)
        self.fields.append(ComboPrefsItem('ui/tab_placement',
            0, None, self.setup_tabs, use_index=True))

        # trigger the toggle callback manually once to set up the right
        # sensitivity for the pref widgets in 'Importing'
        checkbox = xml.get_widget('prefs_import_use_custom')
        checkbox.connect('toggled', self.use_custom_toggled)
        self.use_custom_toggled(checkbox)

        location_button = xml.get_widget('prefs_import_location_button')
        location_entry = xml.get_widget('prefs_import_location')
        location_button.connect('clicked', self.choose_location, location_entry)

        # update the "example" label when values change
        naming = xml.get_widget('prefs_import_naming')
        naming.connect('changed', self.update_example)

        # update the "bitrate" label when quality gets changed
        quality = xml.get_widget('prefs_import_quality')
        bitrate = xml.get_widget('prefs_import_bitrate')
        quality.connect('changed', self.update_bitrate, bitrate)
        import_format.connect('changed', self.update_bitrate, bitrate)
        bitrate.set_no_show_all(True)
        bitrate.hide()
        
        # replaygain toggle handler
        replaygain = xml.get_widget('prefs_replaygain_enabled')
        replaygain.connect('toggled', self.toggle_replaygain)
        
        # proxy server handler
        proxy = xml.get_widget('prefs_proxy_enabled')
        proxy.connect('toggled', self.toggle_proxy)
        xml.get_widget('prefs_proxy_username').set_sensitive(0)
        xml.get_widget('prefs_proxy_password').set_sensitive(0)
        xml.get_widget('prefs_proxy_server').set_sensitive(0)        
        
        # proxy server handler
        proxy = xml.get_widget('prefs_proxy_enabled')
        proxy.connect('toggled', self.toggle_proxy)
        xml.get_widget('prefs_proxy_username').set_sensitive(0)
        xml.get_widget('prefs_proxy_password').set_sensitive(0)
        xml.get_widget('prefs_proxy_server').set_sensitive(0)        
        
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
            'scan_ignore': (ListPrefsItem, ['incomplete']),
            'open_last': (CheckPrefsItem, True),
            'osd/enabled': (CheckPrefsItem, True),
            'osd/w': (PrefsItem, '400', self.osd_adjust_size),
            'osd/h': (PrefsItem, '95', self.osd_adjust_size),
            'lastfm/user': (PrefsItem, ''),
            'lastfm/pass': (CryptedPrefsItem, '', None, self.setup_lastfm),
            'cd_device': (PrefsItem, '/dev/cdrom'),
            'audio_sink': (ComboPrefsItem, 'Use GConf Settings'), # FIXME: i18n?
            'burn_prog': (ComboPrefsItem, (burn_progs and burn_progs[0]) or ''),
            'osd/tray': (CheckPrefsItem, True),
            'osd/bgcolor': (ColorButtonPrefsItem, '#567ea2',
                self.osd_colorpicker),
            'osd/text_color': (ColorButtonPrefsItem, '#ffffff',
                self.osd_colorpicker),
            'osd/text_font': (FontButtonPrefsItem, 'Sans 10',
                self.osd_fontpicker),
            'osd/opacity': (SpinPrefsItem, 80, self.osd_adjust_opacity),
            'ui/use_tray': (CheckPrefsItem, False, None, self.setup_tray),
            'amazon_locale': (ComboPrefsItem, 'us'),
            'wikipedia_locale': (PrefsItem, 'en'),
            'scan_interval': (FloatPrefsItem, 25, None,
                self.setup_scan_interval),
            'download_feeds': (CheckPrefsItem, True),
            'import/format': (ComboPrefsItem, 
                (import_formats and import_formats[0]) or 'MP3'),
            'import/quality': (ComboPrefsItem, "High"), # FIXME: i18n?
            'import/location': (PrefsItem, '', None, self.import_location_changed),
            'import/naming': (PrefsItem, '${artist}/${album}/${artist} - ${title}.${ext}'),
            'import/use_custom': (CheckPrefsItem, False),
            'import/custom': (PrefsItem, ''),
            'replaygain/enabled': (CheckPrefsItem, True),
            'replaygain/album_mode': (CheckPrefsItem, True),
            'replaygain/preamp': (FloatPrefsItem, 0.0),
            'replaygain/fallback': (FloatPrefsItem, 0.0),
            'check_for_updates': (CheckPrefsItem, True),
            'proxy/enabled': (CheckPrefsItem, False),
            'proxy/server': (PrefsItem, ''),
            'proxy/username': (PrefsItem, ''),
            'proxy/password': (CryptedPrefsItem, '', None),
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

    def advanced_toggle_cover(self, item, value):
        if value:
            self.exaile.xml.get_widget('main_cover_frame').show_all()
        else:
            self.exaile.xml.get_widget('main_cover_frame').hide()

    def advanced_toggle_tabbar(self, item, value):
        # value == always show
        self.exaile.playlists_nb.set_show_tabs(
            value or self.exaile.playlists_nb.get_n_pages() > 1)

    def advanced_alphabet_alert(self, item, value):
        """
            Shows an alert when the user changes the "show extended alphabet"
            setting
        """
        # TRANSLATORS: Notification about the "Show Extended Alphabet" setting
        common.info(self.exaile.window, _('Click the "Refresh" button in '
            'the Collection panel to apply this setting.'))

    def advanced_toggle_panel(self, item, value):
        item = item.name.replace('ui/show_', '').replace('_panel', '')
        self.exaile.set_panel_visible(item, value)

    def advanced_toggle_clear_button(self, item, value):
        """
            Hides or shows the clear button
        """
        if value:
            self.exaile.clear_button.show()
        else:
            self.exaile.clear_button.hide()

    def advanced_toggle_stop_button(self, item, value):
        """
            Hides or shows the stop button
        """
        if value:
            self.exaile.stop_button.show()
        else:
            self.exaile.stop_button.hide()        

    def setup_scan_interval(self, widget):
        """
            Makes sure the scan interval is valid, and starts it over with the
            new time value
        """
        value = widget.get_text()

        try:    
            value = float(value)
        except ValueError:  
            common.error(self.exaile.window, "%s is an invalid value "
                "for the library rescan interval" % value)
            return False

        self.exaile.start_scan_interval(value)
        return True

    def update_bitrate(self, widget, bitrate_label):
        """
            Update the bitrate label
        """
        quality = self.xml.get_widget('prefs_import_quality').get_active_text()
        if not quality: return
        quality_label = self.xml.get_widget('quality_label')
        format = self.xml.get_widget('prefs_import_format').get_active_text()

        if format == "FLAC":
            quality_label.set_text(_('Compression Level:'))
            bitrate_label.hide()
        else:
            quality_label.set_text(_('Quality:'))
            bitrate = cd_import.formatdict[format][quality]
            if format == "MP3":
                # TRANSLATORS: For MP3 CBR
                bitrate_label.set_text(_("%d kbps") % bitrate)
            elif format == "MP3 VBR":
                # TRANSLATORS: For MP3 VBR
                bitrate_label.set_text(_("%d mean kbps") % bitrate)
            elif format == "Ogg Vorbis":
                bitrate_label.set_text(str(bitrate))
            bitrate_label.show()


    def import_location_changed(self, widget):
        """
            Scan the new import location for new songs
        """
        items = self.exaile.settings.get_list('search_paths', '')
        path = unicode(widget.get_text(), 'utf-8')
        if not path: return True

        new_items = []
        for item in items:
            if path.startswith(item): 
                # if the import location is a subdir of some existing library path
                # don't scan the tracks since they already are in the library
                self.exaile.settings['import/scan_import_dir'] = False
                return True
            if not item.startswith(path):
                # if the import location is a parent of some existing library path
                # consolidate the list (by not including the old path anymore)
                new_items.append(item)

        self.exaile.settings['search_paths'] = new_items
        self.exaile.library_manager.update_library_add([path], load_tree=True)
        return True

    def choose_location(self, widget, location_entry):
        """
            Sets the "location" preference
        """
        dialog = gtk.FileChooserDialog(_("Choose a directory"),
            self.exaile.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OK, gtk.RESPONSE_OK))
        response = dialog.run()
        dialog.hide()
        
        if response != gtk.RESPONSE_OK:
            return

        path = dialog.get_filename()

        location_entry.set_text(path)

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

    def toggle_replaygain(self, widget, event=None):
        """
            Enables/disables replaygain options.
        """
        items = [xml.get_widget('prefs_replaygain_album_mode'),
                 xml.get_widget('prefs_replaygain_preamp'),
                 xml.get_widget('prefs_replaygain_fallback')]
        to_state = widget.get_active()

        for item in items:
            item.set_sensitive(to_state)

    def toggle_proxy(self, widget, event=None):
        """
            Enables/disables proxy server options.
        """
        items = [xml.get_widget('prefs_proxy_server'),
                 xml.get_widget('prefs_proxy_username'),
                 xml.get_widget('prefs_proxy_password')]
        to_state = widget.get_active()
        
        for item in items:
            item.set_sensitive(to_state)

    def toggle_proxy(self, widget, event=None):
        """
            Enables/disables proxy server options.
        """
        items = [xml.get_widget('prefs_proxy_server'),
                 xml.get_widget('prefs_proxy_username'),
                 xml.get_widget('prefs_proxy_password')]
        to_state = widget.get_active()
        
        for item in items:
            item.set_sensitive(to_state)

    def use_custom_toggled(self, widget, event=None):
        """
            Set sensitivity of widgets when checkbox is toggled
        """
        active = widget.get_active()

        #for w in ['format', 'quality', 'location', 'naming', 'example']:
        for w in ['format', 'quality']:
            xml.get_widget('prefs_import_' + w).set_sensitive(not active)
        xml.get_widget('prefs_import_custom').set_sensitive(active)
        return True

    def update_example(self, widget, *args):
        """
            Updates the 'example' label in the import prefs
        """
        example = xml.get_widget('prefs_import_example')
        #location = xml.get_widget('prefs_import_location')
        #naming = xml.get_widget('prefs_import_naming')

        #dir = location.get_filename()
        path = unicode(widget.get_text(), 'utf-8')

        # TODO: get proper mapping
        mapping = {'artist':'Artist', 'album':'Album', 'num':1, 
                    'title':'Title', 'ext':'mp3', 'date':'2000'}
        template = string.Template(path)
        path = template.safe_substitute(mapping)
        
        # this fails a few times because for some reason dir is often empty 
        # when the pref dialog is constructed... we ignore it
        try:
            #example.set_text(os.path.join(dir, path))
            example.set_text(path)
        except:
            pass

    def setup_lastfm(self, widget):
        """
            Connects to last.fm if the password field isn't empty
        """
        # The audioscrobbler module can handle unicode or UTF-8 str;
        # no need to decode.
        password = widget.get_text()
        if not password: return True
        user = xml.get_widget('prefs_lastfm_user').get_text()

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

    def advanced_setup_tray(self, item, value):
        if value: self.exaile.setup_tray()
        else: self.exaile.remove_tray()

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

    def osd_adjust_opacity(self, widget, event, name, previous):
        """
            Called when the user requests to adjust the opacity (alpha value) of the osd
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
            xl.path.get_data('images', 'nocover.png'))

        return False

    def run(self):
        """
            Runs the dialog
        """
        self.window.show_all()

class BlankClass(object):
    pass
