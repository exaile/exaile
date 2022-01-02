from gi.repository import Gtk, GObject

import xlgui.main
import xl.main
from xl import event, settings, providers
from xl.nls import gettext as _

from . import qb_prefs


class QuickButtons:
    """
    Plugin adds some buttons on the bottom line of the playlists grid to
    change some settings quickly
    """

    name: str = 'QuickButtons'
    """
    Needed for MainWindowStatusBarPane
    """

    self_triggered: bool = False
    """
    Don't repeat yourself.
    Is set to True to prevent resetting from settings.set_option
    """

    _toolbar: Gtk.Box = None

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
            "label": _("Keep playing"),
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
            "label": _("Delay between tracks (in seconds):"),
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
            "depends_on": "equalizer",
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
        "preview_device/audiosink_device": {
            "show_button": "quickbuttons/btn_audio_device_preview",
            "value": None,
            "default": None,
            "widget": None,
            "type": "audio_device_selection",
            "label": _("Preview Device"),
            "tooltip": _("Select preview audio device"),
            "depends_on": "previewdevice",
        },
    }
    """
    Usable options
    """

    def enable(self, exaile: xl.main.Exaile):
        """
        Called on startup of exaile
        """
        self.exaile = exaile

    def disable(self, exaile: xl.main.Exaile):
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

        if self.self_triggered:
            self.self_triggered = False
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
            tbs = qb_toggle(setting, self)

        elif self.options[setting]["type"] == "spin":
            tbs = qb_spinner(setting, self)

        elif self.options[setting]["type"] == "equalizer":
            tbs = qb_equalizer(setting, self)

        elif self.options[setting]["type"] == "audio_device_selection":
            tbs = qb_audio_device(setting, self)

        return self._add_button_to_toolbar(tbs, setting)

    def _add_button_to_toolbar(self, tbs: Gtk.Button, setting: str) -> None:
        show_btn_option = self.options[setting]["show_button"]
        show_btn = settings.get_option(show_btn_option, True)
        if show_btn:
            tbs.show_all()

        self.options[setting]["widget"] = tbs
        self._toolbar.pack_start(tbs, False, True, 0)

    def on_gui_loaded(self):
        """
        Called when the gui is loaded
        """
        if self._toolbar != None:
            self._toolbar.show()
            return

    def create_widget(self, info_area: xlgui.main.MainWindowStatusBarPane):
        self._toolbar = Gtk.Box()

        for k in self.options:
            self.options[k]["value"] = settings.get_option(
                k, self.options[k]["default"]
            )
            self._add_button(k)

        self._toolbar.show()
        return self._toolbar

    def on_exaile_loaded(self):
        providers.register('mainwindow-statusbar-widget', self)
        event.add_callback(self._on_option_set, "playlist_option_set")
        event.add_callback(self._on_option_set, "queue_option_set")
        event.add_callback(self._on_option_set, "player_option_set")
        event.add_callback(self._on_button_activate, "quickbuttons_option_set")

    def get_preferences_pane(self):
        return qb_prefs


plugin_class = QuickButtons


class qb_audio_device(Gtk.MenuButton):
    def __init__(self, setting, qb_instance):
        self._setting = setting
        self._qb = qb_instance
        self._settings = QuickButtons.options[setting]

        self._devices = {}
        """List of all known devices"""

        self._current_device = None
        """Currently selected device"""

        self._button_group = None
        """Button group of the radios"""

        self._devices_to = None
        """Timeout for _set_devices"""

        self.popover = Gtk.Popover()
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox.show_all()
        self.popover.add(self.vbox)

        super().__init__(label=self._settings['label'], popover=self.popover)
        self.set_tooltip_text(self._settings["tooltip"])
        self.connect('toggled', self._on_cb_popup)

    def _set_audio_device(self, button: Gtk.RadioButton) -> None:
        self._qb.self_triggered = True
        if button.get_active() and button.device_id != self._current_device:
            settings.set_option(self._setting, button.device_id)

    def _on_cb_popup(self, widget: Gtk.RadioButton) -> None:
        if widget.get_active():
            self._set_devices()
        elif self._devices_to:
            GObject.source_remove(self._devices_to)

    def _set_devices(self) -> None:
        self._current_device = settings.get_option(
            self._setting, self._settings['default']
        )
        actual_devices = {}

        # @see plugins/previewdevice/previewprefs.py:65
        from xl.player.gst.sink import get_devices

        for name, device_id, _unused in reversed(list(get_devices())):
            actual_devices[device_id] = name
            if device_id not in self._devices:
                widget = self._add_toggle(name, device_id)
                self._devices[device_id] = {'name': name, 'widget': widget}

        for child in self.vbox.get_children():
            if child.device_id not in actual_devices:
                self._devices.pop(child.device_id, None)
                self.vbox.remove(child)

        if self._current_device not in actual_devices:
            self._current_device = 'auto'

        self._devices[self._current_device]["widget"].set_active(True)

        self.vbox.show_all()
        self.vbox.reorder_child(self._devices['auto']['widget'], -1)

        self._devices_to = GObject.timeout_add(1000, self._set_devices)

    def _add_toggle(self, label: str, device_id: str) -> None:
        btn = Gtk.RadioButton(label=label)
        btn.connect('toggled', self._set_audio_device)
        btn.device_id = device_id
        if self._button_group:
            btn.join_group(self._button_group)

        self._button_group = btn
        self.vbox.pack_start(btn, False, True, 10)
        return btn

    def show_all(self) -> None:
        if (
            "depends_on" in self._settings
            and self._settings['depends_on']
            not in self._qb.exaile.plugins.enabled_plugins
        ):
            super().hide()
        else:
            super().show_all()


class qb_equalizer(Gtk.Button):
    def __init__(self, setting, qb_instance):
        self._setting = setting
        self._qb = qb_instance
        self._settings = QuickButtons.options[setting]
        super().__init__()
        self.set_label(self._settings['label'])
        self.set_tooltip_text(self._settings["tooltip"])
        self.connect("clicked", self._on_equalizer_press)

    def _on_equalizer_press(self, widget) -> None:

        if "equalizer" not in self._qb.exaile.plugins.enabled_plugins:
            return None

        eq_plugin_win = self._qb.exaile.plugins.enabled_plugins["equalizer"].window
        if not eq_plugin_win:
            eq_win = GObject.new("EqualizerWindow")
            eq_win.set_transient_for(self._qb.exaile.gui.main.window)
            self._qb.exaile.plugins.enabled_plugins["equalizer"].window = eq_win
            self._equalizer_win = eq_win

        def _destroy(w):
            self._equalizer_win = None
            self._qb.exaile.plugins.enabled_plugins["equalizer"].window = None

        eq_win.connect("destroy", _destroy)
        eq_win.show_all()

    def show_all(self):
        if (
            "depends_on" in self._settings
            and self._settings['depends_on']
            not in self._qb.exaile.plugins.enabled_plugins
        ):
            super().hide()
        else:
            super().show_all()


class qb_spinner(Gtk.SpinButton):
    def __init__(self, setting, qb_instance: QuickButtons):
        self._setting = setting
        self._qb = qb_instance
        self._settings = QuickButtons.options[setting]
        super().__init__()
        self.set_tooltip_text(self._settings["tooltip"])
        self.set_adjustment(Gtk.Adjustment(self._get_delay_value(), 0, 60, 1, 0, 0))
        self.connect("value-changed", self._on_spin, setting)

    def _on_spin(self, widget, setting: str):
        """
        Called when changing the value from spinbutton
        """
        self._qb.self_triggered = True
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
    def __init__(self, setting, qb_instance):
        self._setting = setting
        self._qb = qb_instance
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
        self._qb.self_triggered = True
        settings.set_option(setting, widget.get_active())
