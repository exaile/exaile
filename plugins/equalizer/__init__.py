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
from xl.player.gst.gst_utils import ElementBin
from xlgui.widgets import menu

from xl.nls import gettext as _

import os
import string

# Values from <http://www.xmms.org/faq.php#General3>, adjusted to be less loud
# in general ((mean + max) / 2 = 0).
DEFAULT_PRESETS = [
    ('Custom', 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ('Default', 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ('Classical', 0, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, -5.6, -5.6, -5.6, -8.0),
    ('Club', 0, -5.4, -5.4, 2.6, 0.2, 0.2, 0.2, -2.2, -5.4, -5.4, -5.4),
    ('Dance', 0, 4.8, 2.4, -2.4, -4.8, -4.8, -10.4, -12.0, -12.0, -4.8, -4.8),
    ('Full Bass', 0, -11.5, 6.1, 6.1, 2.1, -1.9, -7.5, -11.5, -13.9, -14.7, -14.7),
    ('Full Bass and Treble', 0, -1.1, -2.7, -8.3, -15.5, -13.1, -6.7, -0.3, 2.9, 3.7, 3.7),
    ('Full Treble', 0, -20.3, -20.3, -20.3, -14.7, -8.3, 0.5, 5.3, 5.3, 5.3, 6.1),
    ('Laptop Speakers and Headphones', 0, -3.9, 2.5, -3.1, -11.9, -11.1, -7.1, -3.9, 0.9, 3.2, 3.2),
    ('Large Hall', 0, 4.3, 4.3, -0.5, -0.5, -6.1, -10.9, -10.9, -10.9, -6.1, -6.1),
    ('Live', 0, -9.0, -4.2, -0.2, 1.4, 1.4, 1.4, -0.2, -1.8, -1.8, -1.8),
    ('Party', 0, 2.2, 2.2, -5.0, -5.0, -5.0, -5.0, -5.0, -5.0, 2.2, 2.2),
    ('Pop', 0, -6.4, 0.0, 2.4, 3.2, 0.8, -4.8, -7.2, -7.2, -6.4, -6.4),
    ('Reggae', 0, -3.6, -3.6, -3.6, -9.2, -3.6, 2.8, 2.8, -3.6, -3.6, -3.6),
    ('Rock', 0, 0.3, -2.9, -13.3, -15.7, -10.9, -3.7, 1.1, 3.5, 3.5, 3.5),
    ('Ska', 0, -9.9, -12.3, -11.5, -7.5, -3.5, -1.9, 1.3, 2.1, 3.7, 2.1),
    ('Soft', 0, -3.6, -6.8, -8.4, -10.8, -8.4, -4.4, -0.4, 1.2, 2.8, 3.6),
    ('Soft Rock', 0, -0.8, -0.8, -2.4, -4.8, -8.8, -10.4, -8.0, -4.8, -2.4, 4.0),
    ('Techno', 0, 1.2, -1.2, -6.8, -12.4, -11.6, -6.8, 1.2, 2.8, 2.8, 2.0),
]


def enable(exaile):
    providers.register("gst_audio_filter", GSTEqualizer)
    if exaile.loading:
        event.add_ui_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)


def _enable(event_type, exaile, nothing):
    """
        Called when the player is loaded.
    """
    global EQ_MAIN
    EQ_MAIN = EqualizerPlugin(exaile)


def disable(exaile):
    providers.unregister("gst_audio_filter", GSTEqualizer)
    global EQ_MAIN
    EQ_MAIN.disable()
    EQ_MAIN = None


class GSTEqualizer(ElementBin):
    """
    Equalizer GST class
    """
    index = 99
    name = "equalizer-10bands"

    def __init__(self):
        ElementBin.__init__(self, name=self.name)

        self.audioconvert = Gst.ElementFactory.make("audioconvert", None)
        self.elements[40] = self.audioconvert

        self.preamp = Gst.ElementFactory.make("volume", None)
        self.elements[50] = self.preamp

        self.eq10band = Gst.ElementFactory.make("equalizer-10bands", None)
        self.elements[60] = self.eq10band

        self.setup_elements()

        event.add_ui_callback(self._on_option_set,
                              "plugin_equalizer_option_set")

        setts = ["band%s" for n in xrange(10)] + ["pre", "enabled"]
        for setting in setts:
            self._on_option_set("plugin_equalizer_option_set", None,
                                "plugin/equalizer/%s" % setting)

    def _on_option_set(self, name, object, data):
        for band in range(10):
            if data == "plugin/equalizer/band%s" % band:
                if settings.get_option("plugin/equalizer/enabled") == True:
                    self.eq10band.set_property("band%s" % band,
                                               settings.get_option("plugin/equalizer/band%s" % band))
                else:
                    self.eq10band.set_property("band%s" % band, 0.0)

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
                    self.eq10band.set_property("band%s" % band,
                                               settings.get_option("plugin/equalizer/band%s" % band))
            else:
                self.preamp.set_property("volume", 1.0)
                for band in range(10):
                    self.eq10band.set_property("band%s" % band, 0.0)

    def dB_to_percent(self, dB):
        return 10**(dB / 10)


class EqualizerPlugin:
    """
    Equalizer plugin class
    """

    def __init__(self, exaile):
        self.window = None

        # add menu item to tools menu
        self.MENU_ITEM = menu.simple_menu_item('equalizer', ['plugin-sep'], _('_Equalizer'),
                                               callback=lambda *x: self.show_gui(exaile))
        providers.register('menubar-tools-menu', self.MENU_ITEM)

        self.presets_path = os.path.join(xdg.get_config_dir(), 'eq-presets.dat')
        self.presets = Gtk.ListStore(str, float, float, float, float,
                                     float, float, float, float, float, float, float)
        self.load_presets()

        self.check_default_settings()

    def check_default_settings(self):

        for band in range(10):
            if settings.get_option("plugin/equalizer/band%s" % band) == None:
                settings.set_option("plugin/equalizer/band%s" % band, 0.0)

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
            'on_main-window_destroy': self.destroy_gui,
            'on_chk-enabled_toggled': self.toggle_enabled,
            'on_combo-presets_changed': self.preset_changed,
            'on_add-preset_clicked': self.add_preset,
            'on_remove-preset_clicked': self.remove_preset,
            'on_pre_format_value': self.adjust_preamp,
            'on_band0_format_value': self.adjust_band,
            'on_band1_format_value': self.adjust_band,
            'on_band2_format_value': self.adjust_band,
            'on_band3_format_value': self.adjust_band,
            'on_band4_format_value': self.adjust_band,
            'on_band5_format_value': self.adjust_band,
            'on_band6_format_value': self.adjust_band,
            'on_band7_format_value': self.adjust_band,
            'on_band8_format_value': self.adjust_band,
            'on_band9_format_value': self.adjust_band
        }

        self.ui = Gtk.Builder()
        self.ui.add_from_file(os.path.join(os.path.dirname(
            os.path.realpath(__file__)), 'equalizer.ui'))
        self.ui.connect_signals(signals)

        self.window = self.ui.get_object('main-window')

        # Setup bands/preamp from current equalizer settings
        for x in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
            self.ui.get_object('band%s' % x).set_value(self.get_band(x))

        self.ui.get_object("pre").set_value(self.get_pre())

        # Put the presets into the presets combobox
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
        return settings.get_option("plugin/equalizer/band%s" % x)

    def get_pre(self):
        """
        Get the current value of pre-amp
        """
        return settings.get_option("plugin/equalizer/pre")

    # Widget callbacks

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
                "plugin/equalizer/band%s" % band))

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

        # If an option other than "Custom" is chosen:
        if i > 0:
            settings.set_option("plugin/equalizer/pre",
                                d.get_value(d.get_iter(i), 1))
            self.ui.get_object("pre").set_value(
                d.get_value(d.get_iter(i), 1))

            for band in range(10):
                settings.set_option("plugin/equalizer/band%s" % band,
                                    d.get_value(d.get_iter(i), band + 2))
                self.ui.get_object("band%s" % band).set_value(
                    d.get_value(d.get_iter(i), band + 2))

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
            for preset in DEFAULT_PRESETS:
                self.presets.append(preset)
