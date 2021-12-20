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

    options = {
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
            "label": _("Main Device"),
            "tooltip": _("Select main audio device"),
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
        for k in self.options:
            show_btn_option = self.options[k]["show_button"]
            if option == show_btn_option:
                if not self.options[k]["widget"]:
                    return
                if settings.get_option(show_btn_option, True):
                    self.options[k]["widget"].show_all()
                else:
                    self.options[k]["widget"].hide()
                break

    def _on_option_set(self, event_name, event_source, option: str) -> None:
        if option not in self.options:
            return

        if self._self_triggered:
            self._self_triggered = False
            return

        self.options[option]["value"] = settings.get_option(option)
        if self.options[option]["type"] == "toggle":
            self.options[option]["widget"].set_active(self.options[option]["value"])
        elif self.options[option]["type"] == "spin":
            self.options[option]["widget"].get_children()[0].set_value(
                self.options[option]["value"]
            )

    def _add_button(self, setting: str) -> None:

        if self.options[setting]["type"] == "toggle":
            tbs = qb_toggle(setting)

        elif self.options[setting]["type"] == "spin":
            tbs = qb_spinner(setting)

        elif self.options[setting]["type"] == "equalizer":
            tbs = qb_equalizer(setting, self._exaile)

        elif self.options[setting]["type"] == "audio_device_selection":
            tbs = qb_audio_device(setting)

        return self._add_button_to_toolbar(tbs, setting)

    def _add_button_to_toolbar(self, tbs, setting) -> None:
        show_btn_option = self.options[setting]["show_button"]
        show_btn = settings.get_option(show_btn_option, True)
        if show_btn:
            tbs.show_all()

        self.options[setting]["widget"] = tbs
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

        for k in self.options:
            self.options[k]["value"] = settings.get_option(
                k, self.options[k]["default"]
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

class qb_audio_device(Gtk.MenuButton):

    def __init__(self, setting):
        self._setting = setting
        self._settings = QuickButtons.options[setting]

        self.popover = Gtk.Popover()
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox.show_all()
        self.popover.add(self.vbox)
        self.popover.set_position(Gtk.PositionType.BOTTOM)

        super().__init__(label=self._settings['label'], popover=self.popover)
        self.set_tooltip_text(self._settings["tooltip"])
        self.connect('toggled', self._on_cb_popup)

    def _set_audio_device(self, button):
        if button.get_active():
            for child in self.vbox.get_children():
                if button == child:
                    settings.set_option(self._setting, button.device_id)
                    continue
                child.set_active(False)
            # button.set_active(True)

    def _on_cb_popup(self, widget):
        if widget.get_active():
            self._set_devices()
        elif self._devices_to:
            GObject.source_remove(self._devices_to)

    def _set_devices(self):
        current = settings.get_option(self._setting, self._settings['default'])
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        # @see plugins/previewdevice/previewprefs.py:65
        from xl.player.gst.sink import get_devices
        for name, device_id, _unused in reversed(list(get_devices())):
            btn = Gtk.ToggleButton(label=name)
            btn.device_id = device_id
            if device_id == current:
                btn.set_active(True)

            btn.connect('toggled', self._set_audio_device)
            self.vbox.pack_end(btn, False, True, 10)
        self.vbox.show_all()
        self.vbox.queue_draw()

        self._devices_to = GObject.timeout_add(1000, self._set_devices)

class qb_equalizer(Gtk.Button):

    def __init__(self, setting, exaile):
        self._setting = setting
        self._settings = QuickButtons.options[setting]
        self._exaile = exaile
        super().__init__()
        self.set_label(self._settings['label'])
        self.set_tooltip_text(self._settings["tooltip"])
        self.connect("clicked", self._on_equalizer_press)

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

class qb_spinner(Gtk.SpinButton):

    def __init__(self, setting):
        self._setting = setting
        self._settings = QuickButtons.options[setting]
        super().__init__()
        self.set_tooltip_text(self._settings["tooltip"])
        self.set_adjustment(Gtk.Adjustment(self._get_delay_value(), 0, 60, 1, 0, 0))
        self.connect("value-changed", self._on_spin, setting)

    def _on_spin(self, widget, setting: str):
        """
        Called when changing the value from spinbutton
        """
        self._self_triggered = True
        self._set_delay_value(widget.get_value_as_int())

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

class qb_toggle(Gtk.ToggleButton):

    def __init__(self, setting):
        self._setting = setting
        self._settings = QuickButtons.options[setting]
        active = self._settings["value"]
        if active != True:
            active = False
        super().__init__()
        self.set_label(self._settings["label"])
        self.set_tooltip_text(self._settings["tooltip"])
        self.set_active(active)
        self.connect("toggled", self._on_toggle, setting)

    def _on_toggle(self, widget, setting: str):
        """
        Called when toggling a button
        """
        settings.set_option(setting, widget.get_active())