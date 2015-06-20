# Copyright (C) 2009-2010 Dave Aitken
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

# support python 2.5
from __future__ import with_statement

from gi.repository import GLib
from gi.repository import Gst
from gi.repository import Gtk

from xl import providers, event, settings, xdg
from xl.player.pipe import ElementBin
from xlgui.widgets import menu

from xl.nls import gettext as _

import os, string

def enable(exaile):
    providers.register("postprocessing_element", GSTEqualizer)
    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)

def _enable(event_type, exaile, nothing):
    """
        Called when the player is loaded.
    """
    global EQ_MAIN
    EQ_MAIN = EqualizerPlugin(exaile)

def disable(exaile):
    providers.unregister("postprocessing_element", GSTEqualizer)
    global EQ_MAIN
    EQ_MAIN.disable()
    EQ_MAIN = None

class GSTEqualizer(ElementBin):
    """
    Equalizer GST class
    """
    index = 99
    name = "equalizer-10bands"
    def __init__(self, player):
        ElementBin.__init__(self, player, name=self.name)

        self.audioconvert = Gst.ElementFactory.make("audioconvert")
        self.elements[40] = self.audioconvert

        self.preamp = Gst.ElementFactory.make("volume")
        self.elements[50] = self.preamp

        self.eq10band = Gst.ElementFactory.make("equalizer-10bands")
        self.elements[60] = self.eq10band

        self.setup_elements()

        event.add_callback(self._on_option_set,
                "plugin_equalizer_option_set")

        setts = ["band%s" for n in xrange(10)] + ["pre", "enabled"]
        for setting in setts:
            self._on_option_set("plugin_equalizer_option_set", None,
                "plugin/equalizer/%s"%setting)

    def _on_option_set(self, name, object, data):
        for band in range(10):
            if data == "plugin/equalizer/band%s"%band:
                if settings.get_option("plugin/equalizer/enabled") == True:
                    self.eq10band.set_property("band%s"%band,
                            settings.get_option("plugin/equalizer/band%s"%band))
                else:
                    self.eq10band.set_property("band%s"%band, 0.0)

        if data == "plugin/equalizer/pre":
            if settings.get_option("plugin/equalizer/enabled") == True:
                self.preamp.set_property("volume", self.dB_to_percent(
                        settings.get_option("plugin/equalizer/pre")))
            else:
                self.preamp.set_property("volume", 1.0)

        if data == "plugin/equalizer/enabled":
            if settings.get_option("plugin/equalizer/enabled") == True:
                self.preamp.set_property("volume", self.dB_to_percent(
                        settings.get_option("plugin/equalizer/pre")))
                for band in range(10):
                    self.eq10band.set_property("band%s"%band,
                            settings.get_option("plugin/equalizer/band%s"%band))
            else:
                self.preamp.set_property("volume", 1.0)
                for band in range(10):
                    self.eq10band.set_property("band%s"%band, 0.0)

    def dB_to_percent(self, dB):
        return 10**(dB / 10)

class EqualizerPlugin:
    """
    Equalizer plugin class
    """

    def __init__(self, exaile):
        self.window = None

        # add menu item to tools menu
        self.MENU_ITEM = menu.simple_menu_item('equalizer', ['plugin-sep'], _('Equalizer'),
            callback=lambda *x: self.show_gui(exaile))
        providers.register('menubar-tools-menu', self.MENU_ITEM)

        self.presets_path = os.path.join(xdg.get_config_dir(), 'eq-presets.dat')
        self.presets = Gtk.ListStore(str, float, float, float, float,
                float, float, float, float, float, float, float)
        self.load_presets()

        self.check_default_settings()

    def check_default_settings(self):

        for band in range(10):
            if settings.get_option("plugin/equalizer/band%s"%band) == None:
                settings.set_option("plugin/equalizer/band%s"%band, 0.0)

        if settings.get_option("plugin/equalizer/pre") == None:
            settings.set_option("plugin/equalizer/pre", 0.0)

        if settings.get_option("plugin/equalizer/enabled") == None:
            settings.set_option("plugin/equalizer/enabled", True)


    def disable(self):

        if self.MENU_ITEM:
            providers.unregister('menubar-tools-menu', self.MENU_ITEM)
            self.MENU_ITEM = None

        if self.window:
            self.window.hide()
            self.window.destroy()

    def load_presets(self):
        """
        Populate the GTK ListStore with presets
        """

    def show_gui(self, exaile):
        """
        Display main window.
        """
        if self.window:
            self.window.present()
            return

        signals = {
                'on_main-window_destroy':self.destroy_gui,
                'on_chk-enabled_toggled':self.toggle_enabled,
                'on_combo-presets_changed':self.preset_changed,
                'on_add-preset_clicked':self.add_preset,
                'on_remove-preset_clicked':self.remove_preset,
                'on_pre_format_value':self.adjust_preamp,
                'on_band0_format_value':self.adjust_band,
                'on_band1_format_value':self.adjust_band,
                'on_band2_format_value':self.adjust_band,
                'on_band3_format_value':self.adjust_band,
                'on_band4_format_value':self.adjust_band,
                'on_band5_format_value':self.adjust_band,
                'on_band6_format_value':self.adjust_band,
                'on_band7_format_value':self.adjust_band,
                'on_band8_format_value':self.adjust_band,
                'on_band9_format_value':self.adjust_band
                }

        self.ui = Gtk.Builder()
        self.ui.add_from_file( os.path.join( os.path.dirname(
                os.path.realpath(__file__)), 'equalizer.ui'))
        self.ui.connect_signals(signals)

        self.window = self.ui.get_object('main-window')

        #Setup bands/preamp from current equalizer settings
        for x in (0,1,2,3,4,5,6,7,8,9):
            self.ui.get_object('band%s' % x).set_value(self.get_band(x))

        self.ui.get_object("pre").set_value(self.get_pre())

        #Put the presets into the presets combobox
        combobox = self.ui.get_object("combo-presets")
        combobox.set_model(self.presets)
        combobox.set_entry_text_column(0)
        combobox.set_active(0)

        self.ui.get_object('chk-enabled').set_active(
                settings.get_option("plugin/equalizer/enabled"))

        self.window.show_all()

    def destroy_gui(self, widget):
        self.window = None

    def get_band(self, x):
        """
        Get the current value of band x
        """
        return settings.get_option("plugin/equalizer/band%s"%x)

    def get_pre(self):
        """
        Get the current value of pre-amp
        """
        return settings.get_option("plugin/equalizer/pre")

    #Widget callbacks

    def adjust_band(self, widget, data):
        """
        Adjust the specified band
        """
        # Buildable.get_name clashes with Widget.get_name. See
        # https://bugzilla.gnome.org/show_bug.cgi?id=591085#c19
        widget_name = Gtk.Buildable.get_name(widget)
        band = widget_name[-1]
        if widget.get_value() != settings.get_option(
                "plugin/equalizer/band" + band):
            settings.set_option("plugin/equalizer/band" + band,
                    widget.get_value())
            self.ui.get_object("combo-presets").set_active(0)

    def adjust_preamp(self, widget, data):
        """
        Adjust the preamp
        """
        if widget.get_value() != settings.get_option("plugin/equalizer/pre"):
            settings.set_option("plugin/equalizer/pre", widget.get_value())
            self.ui.get_object("combo-presets").set_active(0)

    def add_preset(self, widget):

        new_preset = []
        new_preset.append(self.ui.get_object("combo-presets"
                ).get_child().get_text())
        new_preset.append(settings.get_option("plugin/equalizer/pre"))

        for band in range(10):
            new_preset.append(settings.get_option(
                    "plugin/equalizer/band%s"%band))

#        print "EQPLUGIN: debug: ", new_preset
        self.presets.append(new_preset)
        self.save_presets()

    def remove_preset(self, widget):
        entry = self.ui.get_object("combo-presets").get_active()
        if entry > 1:
            self.presets.remove(self.presets.get_iter(entry))
            self.ui.get_object("combo-presets").set_active(0)
            self.save_presets()

    def preset_changed(self, widget):

        d = widget.get_model()
        i = widget.get_active()

        #If an option other than "Custom" is chosen:
        if i > 0:
            settings.set_option("plugin/equalizer/pre",
                    d.get_value( d.get_iter(i), 1))
            self.ui.get_object("pre").set_value(
                    d.get_value( d.get_iter(i), 1))

            for band in range(10):
                settings.set_option("plugin/equalizer/band%s"%band,
                        d.get_value( d.get_iter(i), band+2))
                self.ui.get_object("band%s"%band).set_value(
                        d.get_value( d.get_iter(i), band+2))



    def toggle_enabled(self, widget):
        settings.set_option("plugin/equalizer/enabled", widget.get_active())

    def save_presets(self):
        if os.path.exists(self.presets_path):
            os.remove(self.presets_path)

        with open(self.presets_path, 'w') as f:
            for row in self.presets:
                f.write(row[0] + '\n')
                s = ""
                for i in range(1, 12):
                    s += str(row[i]) + " "

                s += "\n"
                f.write(s)

    def load_presets(self):
        if os.path.exists(self.presets_path):
            with open(self.presets_path, 'r') as f:
                line = f.readline()
                while (line != ""):
                    preset = []
                    preset.append(line[:-1])
                    line = f.readline()

                    vals = string.split(line, " ")

                    for i in range(11):
                        preset.append(float(vals[i]))

                    self.presets.append(preset)
                    line = f.readline()
        else:
            self.presets.append(["Custom",
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
            self.presets.append(["Default",
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
            self.presets.append(["Classical",
                    0, 0, 0, 0, 0, 0, 0, -7.2, -7.2, -7.2, -9.6])
            self.presets.append(["Club",
                    0, 0, 0, 8, 5.6, 5.6, 5.6, 3.2, 0, 0, 0])
            self.presets.append(["Dance",
                    0, 9.6, 7.2, 2.4, 0, 0, -5.6, -7.2, -7.2, 0, 0])
            self.presets.append(["Full Bass",
                    0, -8, 9.6, 9.6, 5.6, 1.6, -4, -8, -10.4, -11.2, -11.2])
            self.presets.append(["Full Bass and Treble",
                    0, 7.2, 5.6, 0, -7.2, -4.8, 1.6, 8, 11.2, 12, 12])
            self.presets.append(["Full Treble",
                    5, -14.6, -14.6, -14.6, -9, -2.6, 6.2, 11, 11, 11, 11.8])
            self.presets.append(["Laptop Speakers and Headphones",
                    0, 4.8, 11.2, 5.6, -3.2, -2.4, 1.6, 4.8, 9.6, 11.9, 11.9])
            self.presets.append(["Large Hall",
                    0, 10.4, 10.4, 5.6, 5.6, 0, -4.8, -4.8, -4.8, 0, 0])
            self.presets.append(["Live",
                    0, -4.8, 0, 4, 5.6, 5.6, 5.6, 4, 2.4, 2.4, 2.4])
            self.presets.append(["Party",
                    0, 7.2, 7.2, 0, 0, 0, 0, 0, 0, 7.2, 7.2])
            self.presets.append(["Pop",
                    0, -1.6, 4.8, 7.2, 8, 5.6, 0, -2.4, -2.4, -1.6, -1.6])
            self.presets.append(["Reggae",
                    0, 0, 0, 0, -5.6, 0, 6.4, 6.4, 0, 0, 0])
            self.presets.append(["Rock",
                    0, 8, 4.8, -5.6, -8, -3.2, 4, 8.8, 11.2, 11.2, 11.2])
            self.presets.append(["Ska",
                    0, -2.4, -4.8, -4, 0, 4, 5.6, 8.8, 9.6, 11.2, 9.6])
            self.presets.append(["Soft",
                    0, 4.8, 1.6, 0, -2.4, 0, 4, 8, 9.6, 11.2, 12])
            self.presets.append(["Soft Rock",
                    0, 4, 4, 2.4, 0, -4, -5.6, -3.2, 0, 2.4, 8.8])
            self.presets.append(["Techno",
                    0, 8, 5.6, 0, -5.6, -4.8, 0, 8, 9.6, 9.6, 8.8])
