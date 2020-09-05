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


import logging
import os

from gi.repository import Gst
from gi.repository import Gtk

from xl import providers, event, settings, xdg
from xl.player.gst.gst_utils import ElementBin
from xl.nls import gettext as _
from xlgui.guiutil import GtkTemplate
from xlgui.widgets import menu

logger = logging.getLogger('equalizer')


def isclose(float_a, float_b, rel_tol=1e-09, abs_tol=0.0):
    """
    copied from python 3.5, where this function was introduced to the math module
    """
    return abs(float_a - float_b) <= max(
        rel_tol * max(abs(float_a), abs(float_b)), abs_tol
    )


# Values from <http://www.xmms.org/faq.php#General3>, adjusted to be less loud
# in general ((mean + max) / 2 = 0).
DEFAULT_PRESETS = [
    # fmt: off
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
    # fmt: on
]


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

        event.add_ui_callback(self._on_option_set, "plugin_equalizer_option_set")

        setts = ["band%s" for _number in range(10)] + ["pre", "enabled"]
        for setting in setts:
            self._on_option_set(
                "plugin_equalizer_option_set", None, "plugin/equalizer/%s" % setting
            )

    def _on_option_set(self, _name, _object, data):
        for band in range(10):
            if data == "plugin/equalizer/band%s" % band:
                if settings.get_option("plugin/equalizer/enabled") is True:
                    self.eq10band.set_property(
                        "band%s" % band,
                        settings.get_option("plugin/equalizer/band%s" % band),
                    )
                else:
                    self.eq10band.set_property("band%s" % band, 0.0)

        if data == "plugin/equalizer/pre":
            if settings.get_option("plugin/equalizer/enabled") is True:
                self.preamp.set_property(
                    "volume",
                    self.dB_to_percent(settings.get_option("plugin/equalizer/pre")),
                )
            else:
                self.preamp.set_property("volume", 1.0)

        if data == "plugin/equalizer/enabled":
            if settings.get_option("plugin/equalizer/enabled") is True:
                self.preamp.set_property(
                    "volume",
                    self.dB_to_percent(settings.get_option("plugin/equalizer/pre")),
                )
                for band in range(10):
                    self.eq10band.set_property(
                        "band%s" % band,
                        settings.get_option("plugin/equalizer/band%s" % band),
                    )
            else:
                self.preamp.set_property("volume", 1.0)
                for band in range(10):
                    self.eq10band.set_property("band%s" % band, 0.0)

    @staticmethod
    def dB_to_percent(dB):
        return 10 ** (dB / 10)


@GtkTemplate('equalizer.ui', relto=__file__)
class EqualizerWindow(Gtk.Window):
    __gtype_name__ = 'EqualizerWindow'

    PRESETS_PATH = os.path.join(xdg.get_config_dir(), 'eq-presets.dat')

    (
        band0,
        band1,
        band2,
        band3,
        band4,
        band5,
        band6,
        band7,
        band8,
        band9,
        chk_enabled,
        combo_presets,
        presets,
        pre,
    ) = GtkTemplate.Child.widgets(14)

    def __init__(self):
        Gtk.Window.__init__(self)
        self.init_template()
        self.pre.set_value(settings.get_option("plugin/equalizer/pre"))
        self.chk_enabled.set_active(settings.get_option("plugin/equalizer/enabled"))
        # Setup bands/preamp from current equalizer settings
        for number in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
            band = getattr(self, 'band%s' % number)
            band.set_value(self.get_band(number))
        self.combo_presets.set_entry_text_column(0)
        self.combo_presets.set_active(0)
        self.load_presets()

    @staticmethod
    def get_band(band_number):
        """
        Get the current value of band x
        """
        return settings.get_option("plugin/equalizer/band%s" % band_number)

    @GtkTemplate.Callback
    def adjust_band(self, widget):
        """
        Adjust the specified band
        """
        # Buildable.get_name clashes with Widget.get_name. See
        # https://bugzilla.gnome.org/show_bug.cgi?id=591085#c19
        widget_name = Gtk.Buildable.get_name(widget)
        band = widget_name[-1]
        settings_value = settings.get_option("plugin/equalizer/band" + band)
        if not isclose(widget.get_value(), settings_value):
            settings.set_option("plugin/equalizer/band" + band, widget.get_value())
            self.combo_presets.set_active(0)

    @GtkTemplate.Callback
    def adjust_preamp(self, widget):
        """
        Adjust the preamp
        """
        if widget.get_value() != settings.get_option("plugin/equalizer/pre"):
            settings.set_option("plugin/equalizer/pre", widget.get_value())
            self.combo_presets.set_active(0)

    @GtkTemplate.Callback
    def add_preset(self, _widget):

        new_preset = []
        new_preset.append(self.combo_presets.get_child().get_text())
        new_preset.append(settings.get_option("plugin/equalizer/pre"))

        for band in range(10):
            new_preset.append(settings.get_option("plugin/equalizer/band%s" % band))

        self.presets.append(new_preset)
        self.save_presets()

    @GtkTemplate.Callback
    def remove_preset(self, _widget):
        entry = self.combo_presets.get_active()
        if entry > 1:
            self.presets.remove(self.presets.get_iter(entry))
            self.combo_presets.set_active(0)
            self.save_presets()

    @GtkTemplate.Callback
    def preset_changed(self, widget):
        model = widget.get_model()
        index = widget.get_active()

        # If an option other than "Custom" is chosen:
        if index > 0:
            settings.set_option(
                "plugin/equalizer/pre", model.get_value(model.get_iter(index), 1)
            )
            self.pre.set_value(model.get_value(model.get_iter(index), 1))

            for band in range(10):
                settings.set_option(
                    "plugin/equalizer/band%s" % band,
                    model.get_value(model.get_iter(index), band + 2),
                )
                band_widget = getattr(self, "band%s" % band)
                band_widget.set_value(model.get_value(model.get_iter(index), band + 2))

    @GtkTemplate.Callback
    def check_enabled(self, widget):
        settings.set_option("plugin/equalizer/enabled", widget.get_active())

    def save_presets(self):
        if os.path.exists(self.PRESETS_PATH):
            os.remove(self.PRESETS_PATH)

        with open(self.PRESETS_PATH, 'w') as config_file:
            for row in self.presets:
                config_file.write(row[0] + '\n')
                line = "".join(str(row[i]) + " " for i in range(1, 12))
                line += "\n"
                config_file.write(line)

    def load_presets(self):
        """
        Populate the GTK ListStore with presets
        """
        load_defaults = True
        if os.path.exists(self.PRESETS_PATH):
            try:
                with open(self.PRESETS_PATH, 'r') as presets_file:
                    line = presets_file.readline()
                    while line != "":
                        preset = []
                        preset.append(line[:-1])
                        line = presets_file.readline()
                        vals = line.split(" ")
                        for i in range(11):
                            preset.append(float(vals[i]))

                        self.presets.append(preset)
                        line = presets_file.readline()
            except Exception:
                logger.exception(
                    "Error loading equalizer presets, reverting to defaults"
                )
            else:
                load_defaults = False

        if load_defaults:
            for preset in DEFAULT_PRESETS:
                self.presets.append(preset)


class EqualizerPlugin:
    """
    Equalizer plugin class
    """

    def __init__(self):
        self.window = None
        self.__menu_item = None
        self.__exaile = None
        self.check_default_settings()

    @staticmethod
    def check_default_settings():
        for band in range(10):
            if settings.get_option("plugin/equalizer/band%s" % band) is None:
                settings.set_option("plugin/equalizer/band%s" % band, 0.0)

        if settings.get_option("plugin/equalizer/pre") is None:
            settings.set_option("plugin/equalizer/pre", 0.0)

        if settings.get_option("plugin/equalizer/enabled") is None:
            settings.set_option("plugin/equalizer/enabled", True)

    def disable(self, _exaile):
        if self.__menu_item:
            providers.unregister('menubar-tools-menu', self.__menu_item)
            self.__menu_item = None
        if self.window:
            self.window.hide()
            self.window.destroy()
            self.window = None
        providers.unregister("gst_audio_filter", GSTEqualizer)

    def __show_gui(self):
        """
        Display main window.
        """
        if not self.window:
            self.window = EqualizerWindow()
            self.window.set_transient_for(self.__exaile.gui.main.window)

            def _destroy(w):
                self.window = None

            self.window.connect('destroy', _destroy)
        self.window.show_all()

    def enable(self, exaile):
        providers.register("gst_audio_filter", GSTEqualizer)
        self.__exaile = exaile

    def on_gui_loaded(self):
        """
        Called when the player is loaded.
        """
        # add menu item to tools menu
        self.__menu_item = menu.simple_menu_item(
            'equalizer',
            ['plugin-sep'],
            _('_Equalizer'),
            callback=lambda *x: self.__show_gui(),
        )
        providers.register('menubar-tools-menu', self.__menu_item)


plugin_class = EqualizerPlugin
