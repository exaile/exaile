from gi.repository import Gtk, GObject
from xl import event, settings, providers
from xl.nls import gettext as _

from . import qb_prefs


class QuickButtons:
    """
    Plugin adds some buttons on the bottom line of the playlists grid to
    change some settings quickly
    """

    _self_triggered = False
    """
    Don't repeat yourself.
    Is set to True to prevent resetting from settings.set_option
    """

    _toolbar = None
    _equalizer_win = None

    _options = {
        "playlist/enqueue_by_default": {
            "show_button": "quickbuttons/btn_enqueue_by_default",
            "value": None,
            "default": False,
            "widget": None,
            "type": "toggle",
            "label": _("Enqueue"),
            "tooltip": _("Queue tracks by default instead of playing them"),
        },
        "queue/disable_new_track_when_playing": {
            "show_button": "quickbuttons/btn_disable_new_track_when_playing",
            "value": None,
            "default": False,
            "widget": None,
            "type": "toggle",
            "label": "Keep playing",
            "tooltip": _("Disallow playing new tracks when another track is playing"),
        },
        "queue/remove_item_when_played": {
            "show_button": "quickbuttons/btn_remove_item_when_played",
            "value": None,
            "default": True,
            "widget": None,
            "type": "toggle",
            "label": _("Auto-Remove"),
            "tooltip": _("Remove track from queue upon playback"),
        },
        "player/auto_advance": {
            "show_button": "quickbuttons/btn_auto_advance",
            "value": None,
            "default": True,
            "widget": None,
            "type": "toggle",
            "label": _("Auto-Advance"),
            "tooltip": _("Automatically advance to the next track"),
        },
        "player/auto_advance_delay": {
            "show_button": "quickbuttons/btn_auto_advance_delay",
            "value": None,
            "default": 0,
            "widget": None,
            "type": "spin",
            "label": _("Delay"),
            "tooltip": _("Delay between tracks (in seconds):"),
        },
        "equalizer": {
            "show_button": "quickbuttons/btn_equalizer",
            "value": None,
            "default": None,
            "widget": None,
            "type": "equalizer",
            "label": _("EQ"),
            "tooltip": _("Equalizer"),
            "depends_on": "equalizer"
        },
        "player/audiosink_device": {
            "show_button": "quickbuttons/btn_audio_device",
            "value": None,
            "default": 'auto',
            "widget": None,
            "type": "audio_device_selection",
            "label": _("EQ"),
            "tooltip": _("Equalizer"),
        },
        # "preview_device/audiosink_device": {
        #     "show_button": "quickbuttons/btn_audio_device_preview",
        #     "value": None,
        #     "default": None,
        #     "widget": None,
        #     "type": "audio_device_selection",
        #     "label": _("EQ"),
        #     "tooltip": _("Equalizer"),
        # },
    }
    """
    Usable options
    """

    def enable(self, exaile):
        """
        Called on startup of exaile
        """
        self._exaile = exaile

        event.add_callback(self._on_option_set, "playlist_option_set")
        event.add_callback(self._on_option_set, "queue_option_set")
        event.add_callback(self._on_option_set, "player_option_set")
        event.add_callback(self._on_button_activate, "quickbuttons_option_set")

    def disable(self, exaile):
        self._toolbar.hide()
        event.remove_callback(self._on_option_set, "playlist_option_set")
        event.remove_callback(self._on_option_set, "queue_option_set")
        event.remove_callback(self._on_option_set, "player_option_set")

    def _on_button_activate(self, event_name, event_source, option: str) -> None:
        for k in self._options:
            show_btn_option = self._options[k]["show_button"]
            if option == show_btn_option:
                if not self._options[k]["widget"]:
                    return
                if settings.get_option(show_btn_option, True):
                    self._options[k]["widget"].show_all()
                else:
                    self._options[k]["widget"].hide()
                break

    def _on_option_set(self, event_name, event_source, option: str) -> None:
        if option not in self._options:
            return

        if self._self_triggered:
            self._self_triggered = False
            return

        self._options[option]["value"] = settings.get_option(option)
        if self._options[option]["type"] == "toggle":
            self._options[option]["widget"].set_active(self._options[option]["value"])
        elif self._options[option]["type"] == "spin":
            self._options[option]["widget"].get_children()[0].set_value(
                self._options[option]["value"]
            )

    def _on_toggle(self, widget, setting: str):
        """
        Called when toggling a button
        """
        self._self_triggered = True
        settings.set_option(setting, widget.get_active())

    def _on_spin(self, widget, setting: str):
        """
        Called when changing the value from spinbutton
        """
        self._self_triggered = True
        self._set_delay_value(widget.get_value_as_int())

    def _on_equalizer_press(self, widget) -> None:

        if "equalizer" not in self._exaile.plugins.enabled_plugins:
            return None

        eq_plugin_win = self._exaile.plugins.enabled_plugins["equalizer"].window
        if not eq_plugin_win:
            eq_win = GObject.new("EqualizerWindow")
            eq_win.set_transient_for(self._exaile.gui.main.window)
            self._exaile.plugins.enabled_plugins["equalizer"].window = eq_win
            self._equalizer_win = eq_win

        def _destroy(w):
            self._equalizer_win = None
            self._exaile.plugins.enabled_plugins["equalizer"].window = None

        eq_win.connect("destroy", _destroy)
        eq_win.show_all()

    def _on_cb_changed(self, combo, setting):
        active = combo.get_active_id()
        if active == None:
            return
        settings.set_option(setting, active)

    def _on_cb_popup(self, combo, setting, dummy):
        # if combo.get_property('popup_shown'):
        #     self._set_devices(combo, dummy)
        pass

    def _set_devices(self, tbs, setting):
        # @see plugins/previewdevice/previewprefs.py:65
        from xl.player.gst.sink import get_devices
        tbs.remove_all()
        for device_name, device_id, _unused in list(get_devices()):
            tbs.append(device_id, device_name)

        GObject.timeout_add(1000, self._set_devices, tbs, setting)

    def _get_delay_value(self) -> int:
        """
        Get the current delay value in seconds as int
        """
        value = settings.get_option("player/auto_advance_delay")
        if value == None:
            value = 0
        value = value / 1000
        return int(value)

    def _set_delay_value(self, value: int) -> None:
        """
        Set the delay value in ms
        """
        value = value * 1000
        settings.set_option("player/auto_advance_delay", value)

    def _add_button(self, setting: str) -> None:

        if self._options[setting]["type"] == "toggle":
            active = self._options[setting]["value"]
            if active != True:
                active = False
            tbs = Gtk.ToggleButton()
            tbs.set_label(self._options[setting]["label"])
            tbs.set_active(active)
            tbs.connect("toggled", self._on_toggle, setting)

        elif self._options[setting]["type"] == "spin":
            tbs = Gtk.SpinButton()
            tbs.set_adjustment(Gtk.Adjustment(self._get_delay_value(), 0, 60, 1, 0, 0))
            tbs.connect("value-changed", self._on_spin, setting)

        elif self._options[setting]["type"] == "equalizer":
            if "equalizer" not in self._exaile.plugins.enabled_plugins:
                return None
            tbs = Gtk.Button()
            tbs.set_label(_("EQ"))
            tbs.connect("clicked", self._on_equalizer_press)

        elif self._options[setting]["type"] == "audio_device_selection":

            tbs = Gtk.ComboBoxText()
            self._set_devices(tbs, setting)
            val = self._options[setting]["value"]

            tbs.set_active_id(val)
            tbs.set_sensitive(True)
            tbs.set_property('active', True)
            tbs.set_property('can-focus', 0)

            GObject.timeout_add(1000, self._set_devices, tbs, setting)

            # tbs.connect("notify::popup-shown", self._on_cb_popup, setting)
            tbs.connect("changed", self._on_cb_changed, setting)

        return self._add_button_to_toolbar(tbs, setting)

    def _add_button_to_toolbar(self, tbs, setting) -> None:
        tbs.set_tooltip_text(self._options[setting]["tooltip"])

        show_btn_option = self._options[setting]["show_button"]
        show_btn = settings.get_option(show_btn_option, True)
        if show_btn:
            tbs.show_all()

        self._options[setting]["widget"] = tbs
        self._toolbar.pack_start(tbs, False, True, 0)

    def on_gui_loaded(self):
        """
        Called when the gui is loaded
        Before that there is no status bar
        """

        if self._toolbar != None:
            self._toolbar.show_all()
            return

        self._status_bar = self._exaile.gui.builder.get_object("status_bar")
        self._toolbar = Gtk.Box()

        for k in self._options:
            self._options[k]["value"] = settings.get_option(
                k, self._options[k]["default"]
            )
            self._add_button(k)

        self._toolbar.show_all()
        self._status_bar.pack_start(self._toolbar, False, True, 0)
        self._status_bar.reorder_child(self._toolbar, 0)

    def on_exaile_loaded(self):
        pass

    def get_preferences_pane(self):
        return qb_prefs


plugin_class = QuickButtons
