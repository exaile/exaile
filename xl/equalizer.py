# Copyright (C) 2006 Adam Olsen
# Copyright (C) 2007 Sayamindu Dasgupta
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

from gettext import gettext as _

import ConfigParser, os
import gtk, gtk.glade
import xl.path

def get_active_text(combobox):
    model = combobox.get_model()
    active = combobox.get_active()
    if active < 0:
        return None
    return unicode(model[active][0], 'utf-8')

class EqualizerWindow(object):
    """
        Equalizer Settings Window
    """
    def __init__(self, exaile):
        """
            Inizializes the window
        """
        self.exaile = exaile
        self.equalizer = exaile.player.equalizer
        self.xml = gtk.glade.XML('exaile.glade', 'EqualizerWindow', 'exaile')
        self.dialog = self.xml.get_widget('EqualizerWindow')
        self.dialog.set_transient_for(self.exaile.window)

        self.get_widgets()

        self.delete.set_sensitive(False) # We can't let the user delete default presets
        self.save.set_sensitive(False)
        self.default_presets = []


        self._scale_changed_ids = []
        for scale in self.scales:
            self._scale_changed_ids.append(scale.connect('value_changed', self.on_value_changed_cb))
        self.close.connect('clicked', lambda e: self.dialog.destroy())
        self.save.connect('clicked',  self.save_preset)
        self.delete.connect('clicked', self.delete_preset)
        self.import_btn.connect('clicked', self.import_preset)
        self._preset_changed_id = self.preset_chooser.connect('changed', self.preset_changed_cb)
        self.setup_preset_chooser()
        
        self.setup_equalizer()
        self.dialog.show()

    def get_widgets(self):
        """
            Gets all widgets from the glade definition file
        """
        xml = self.xml
        self.scales = [xml.get_widget('eq_scale%02d' % i) for i in xrange(1, 11)]
        self.close = xml.get_widget('eq_close_button')
        self.preset_chooser = xml.get_widget('eq_preset_combobox')
        self.save = xml.get_widget('eq_save_button')
        self.delete = xml.get_widget('eq_del_button')
        self.import_btn = xml.get_widget('eq_import_button')

    def setup_equalizer(self):
        """
            Gets the previous equalizer values from the settings
        """
        self.band_values = self.exaile.settings.get_list('equalizer/band-values', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        self.apply_band_values()
        self.update_scales()

    def update_scales(self):
        """
            Changes the values of the scales (updates the GUI)
        """
        i = 0
        # We need to block the callback for 'changed' first
        for id in self._scale_changed_ids:
            self.scales[i].handler_block(id)
            i = i + 1
        i = 0
        for scale in self.scales:
            scale.set_value(self.band_values[i])
            i = i + 1
        # Done. Now unblock the callbacks
        i = 0
        for id in self._scale_changed_ids:
            self.scales[i].handler_unblock(id)
            i = i + 1


    def on_value_changed_cb(self, *e):
        """
            Callback for value change in the scales
        """
        self.band_values = []
        for scale in self.scales: #FIXME: Not a very optimal way to do stuff
            self.band_values.append(scale.get_value())
        self.apply_band_values()
        if self.custom == True:
            self.preset_chooser.set_active(0)
        self.custom = True # Will be reset by apply_preset_by_name() if required 

    def preset_changed_cb(self, combobox):
         preset = get_active_text(combobox)
         self.apply_preset_by_name(preset)
         # The following block enables/disabled the save/delete button as and when reqd.
         if preset in self.default_presets:
             self.delete.set_sensitive(False)
             self.save.set_sensitive(False)
         else:
             self.delete.set_sensitive(True) # This is not a builtin preset, user can delete it
             self.save.set_sensitive(True)
         if preset == "Custom":
             self.delete.set_sensitive(False)

    def apply_preset_by_name(self, name):
        """ 
            Applies a given preset
        """
        if name == 'Custom':
            self.custom = True
        elif name in self.default_presets:
            self.custom = False
            config = ConfigParser.ConfigParser()
            config.read(['equalizer.ini'])
            presets = config.sections()
            presets.sort()
            for preset in presets:
                if config.get(preset, "name") == name:
                    self.band_values = eval(config.get(preset, "value"))
        else:
            option = 'equalizer/eqpreset_' + name.replace(' ', '_').lower()
            self.band_values = self.exaile.settings.get_list(option)[1:]           
                    
        self.exaile.settings.set_str('equalizer/last-preset', name)
        self.apply_band_values()
        self.update_scales()


    def setup_preset_chooser(self):
        config = ConfigParser.ConfigParser()
        config.read(['equalizer.ini']) # The default presets
        presets = config.sections()

        presets.sort()
        for preset in presets:
            self.preset_chooser.append_text(config.get(preset, "name"))
            self.default_presets.append(config.get(preset, "name"))

        cpresets = self.exaile.settings.config.options("equalizer") # The custom/imported presets
        cpresets.sort()
        for cpreset in cpresets:
            if 'eqpreset_' in cpreset:
                self.preset_chooser.append_text(self.exaile.settings.get_list(('equalizer/'+cpreset))[0])

        last_preset = self.exaile.settings.get_str('equalizer/last-preset')

        if last_preset == "Custom":
            self.custom = True
        else:
            self.custom = False

        # Block the signal handler apply_preset_by_name()
        self.preset_chooser.handler_block(self._preset_changed_id)

        model = self.preset_chooser.get_model()
        i = 0
        for m in model:
            if (m[0] == last_preset):
                self.preset_chooser.set_active(i)
            i = i + 1

        # Unblock the handler 
        self.preset_chooser.handler_unblock(self._preset_changed_id)

        # Enable/disable the buttons as and when required
        if last_preset in self.default_presets:
            self.delete.set_sensitive(False)
            self.save.set_sensitive(False)
        else:
            self.delete.set_sensitive(True) # This is not a builtin preset, user can delete it
            self.save.set_sensitive(True)
        if last_preset == "Custom":
            self.delete.set_sensitive(False)

        

    def apply_band_values(self):
        i = 0
        if self.equalizer != None:
            for v in self.band_values:
                self.equalizer.set_property(('band'+str(i)), v)
                i = i + 1
            self.exaile.settings.set_list('equalizer/band-values', self.band_values)
            return
        else:
            return

    def import_preset(self, *e):
        PresetImport(self)

    def save_preset(self, *e):
        PresetSave(self)

    def delete_preset(self, *e):

        #TODO: Add a confirmation Dialog

        name = get_active_text(self.preset_chooser)
        active = self.preset_chooser.get_active()

        # Delete the combobox entry first
        self.preset_chooser.remove_text(active)
        
        # Delete the settings from settings.ini
        option = 'eqpreset_' + name.replace(' ', '_').lower()
        self.exaile.settings.config.remove_option('equalizer', option)

        # Go back to Custom
        self.preset_chooser.set_active(0)
        self.apply_preset_by_name("Custom")
         
class PresetImport(object):
    def __init__(self, eq):
        """
            Imports a .eqf file
        """
        self.eq = eq
        self.xml = gtk.glade.XML('exaile.glade', 'EqualizerImportPreset', 'exaile')
        self.dlg = self.xml.get_widget('EqualizerImportPreset')
        self.dlg.set_transient_for(eq.dialog)

        self.name_widget = self.xml.get_widget('eq_preset_name_entry')

        self.import_btn = self.xml.get_widget('eq_preset_import_btn')
        self.import_btn.set_sensitive(False) # Since there's nothing in the text entry yet

        self.cancel_btn = self.xml.get_widget('eq_preset_cancel_btn')

        self.filechooser_btn = self.xml.get_widget('eq_preset_filechooser_btn')
        self.filechooser_btn.connect("selection-changed", self.enable_import)

        filter = gtk.FileFilter()
        filter.set_name(_("Winamp EQF files"))
        filter.add_pattern("*.eqf")
        self.filechooser_btn.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name(_("All files"))
        filter.add_pattern("*")
        self.filechooser_btn.add_filter(filter)
        self.filechooser_btn.set_current_folder(xl.path.home)

        self.name_widget.connect('changed', self.enable_import)

        self.import_btn.connect('clicked', self.import_preset)
        self.cancel_btn.connect('clicked', lambda e: self.dlg.destroy())
        self.dlg.show_all()

    def enable_import(self, *e):
        name = unicode(self.name_widget.get_text(), 'utf-8')
        filename = self.filechooser_btn.get_filename()

        if (name and filename is not None):
            self.import_btn.set_sensitive(True)
        else:
            self.import_btn.set_sensitive(False)

    def import_preset(self, *e):
        filename = self.filechooser_btn.get_filename()

        band_values = self.parse_eqf(filename)

        for i in band_values:
            self.eq.band_values.append(i)

        name = self.name_widget.get_text()

        band_values.insert(0, name)
    
        name = name.replace(' ', '_').lower()
        #FIXME: Check for duplicate names
        self.eq.exaile.settings.set_list(('equalizer/eqpreset_'+name), band_values)

        self.eq.preset_chooser.append_text(band_values[0])
        self.eq.preset_chooser.set_active(len(self.eq.preset_chooser.get_model())-1)

        self.dlg.destroy()


    def parse_eqf(self, filename):
        # Stolen from XMMS

        f = open(filename, 'rb')
        header = f.read(31)

        if header.startswith('Winamp EQ library file v1.1'):
            tmp = f.read(257) # this contains the name - seems to be some problem with this
            b = f.read(11)

            preamp = 20.0 - ((ord(b[10])*40.0)/64.0)
    
            bands = []
            for i in b[0:10]:
                bands.append((20.0 - ((ord(i)*40.0)/64.0))/20.0)
        else:
            #TODO: Turn this into a proper error dialog
            print "The file does not seem to be a valid EQF file"

        return bands



        
class PresetSave(object):
    def __init__(self, eq):
        """
            Saves a preset in $HOME/.exaile/settings.ini
        """
        
        #TODO: Alert the user if the name is already being used.

        self.eq = eq

        self.xml = gtk.glade.XML('exaile.glade', 'EqualizerSavePreset', 'exaile')
        self.dlg = self.xml.get_widget('EqualizerSavePreset')
        self.dlg.set_transient_for(eq.dialog)

        self.name_widget = self.xml.get_widget('name_entry')
        self.save_btn = self.xml.get_widget('eq_save_save')
        self.save_btn.set_sensitive(False) # Since there's nothing in the text entry yet
        self.cancel_btn = self.xml.get_widget('eq_save_cancel')

        self.name_widget.connect('changed', self.enable_save)

        self.save_btn.connect('clicked', self.do_real_save_preset)
        self.cancel_btn.connect('clicked', lambda e: self.dlg.destroy())

        self.dlg.show_all()

    def do_real_save_preset(self, *e):
        band_values = []
        for scale in self.eq.scales: #FIXME: Not a very optimal way to do stuff
            band_values.append(scale.get_value())

        name = self.name_widget.get_text()

        band_values.insert(0, name)
    
        name = name.replace(' ', '_').lower()
        #FIXME: Check for duplicate names
        self.eq.exaile.settings.set_list(('equalizer/eqpreset_'+name), band_values)

        self.eq.preset_chooser.append_text(band_values[0])
        self.eq.preset_chooser.set_active(len(self.eq.preset_chooser.get_model())-1)

        self.dlg.destroy()

    def enable_save(self, *e):
        name = self.name_widget.get_text()
        self.save_btn.set_sensitive(bool(name))
