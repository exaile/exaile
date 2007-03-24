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

import pygtk
pygtk.require('2.0')
import gtk, gtk.glade
import ConfigParser

def get_active_text(combobox):
    model = combobox.get_model()
    active = combobox.get_active()
    if active < 0:
        return None
    return model[active][0]

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

        self._scale_changed_ids = []
        for scale in self.scales:
            self._scale_changed_ids.append(scale.connect('value_changed', self.on_value_changed_cb))
        self.close.connect('clicked', lambda e: self.dialog.destroy())
        self._preset_changed_id = self.preset_chooser.connect('changed', self.preset_changed_cb)
        self.setup_preset_chooser()

        self.setup_equalizer()
        self.dialog.show()

    def get_widgets(self):
        """
            Gets all widgets from the glade definition file
        """
        xml = self.xml
        self.scales = [xml.get_widget('eq_scale01'), xml.get_widget('eq_scale02'), xml.get_widget('eq_scale03'),
                 xml.get_widget('eq_scale04'), xml.get_widget('eq_scale05'), xml.get_widget('eq_scale06'), 
                 xml.get_widget('eq_scale07'), xml.get_widget('eq_scale08'), xml.get_widget('eq_scale09'), 
                 xml.get_widget('eq_scale10')]
        self.close = xml.get_widget('eq_close_button')
        self.preset_chooser = xml.get_widget('eq_preset_combobox')

    def setup_equalizer(self):
        """
            Gets the previous equalizer values from the settings
        """
        self.band_values = self.exaile.settings.get_list('band-values', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
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
        self.exaile.settings.set_list('band-values', self.band_values)
        if self.custom == True:
            self.preset_chooser.set_active(0)
        self.custom = True # Will be reset by apply_preset_by_name() if required 

    def preset_changed_cb(self, combobox):
         preset = get_active_text(combobox)
         self.apply_preset_by_name(preset)

    def apply_preset_by_name(self, name):
        """ 
            Applies a given preset
        """
        if name == 'custom':
            self.custom = True
        else:
            self.custom = False
            config = ConfigParser.ConfigParser()
            config.read(['equalizer.ini'])
            presets = config.sections()
            presets.sort()
            for preset in presets:
                if config.get(preset, "name") == name:
                    self.band_values = eval(config.get(preset, "value"))
                    self.exaile.settings.set_str('last-preset', name)

        self.apply_band_values()
        self.exaile.settings.set_list('band-values', self.band_values)
        self.update_scales()

    def setup_preset_chooser(self):
        config = ConfigParser.ConfigParser()
        config.read(['equalizer.ini'])
        presets = config.sections()
        presets.sort()
        for preset in presets:
            self.preset_chooser.append_text(config.get(preset, "name"))
        last_preset = self.exaile.settings.get_str('last-preset')
        self.custom = True #FIXME: This actually depends on the last_preset value

    def apply_band_values(self):
        i = 0
        if self.equalizer != None:
            for v in self.band_values:
                self.equalizer.set_property(('band'+str(i)), v)
                i = i + 1
            return
        else:
            return

