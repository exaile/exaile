
from gi.repository import Gtk
from xl import event, settings
from xl.nls import gettext as _

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

    _options = {
        'playlist/enqueue_by_default': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'enq',
                                        'tooltip': 'Queue tracks by default instead of playing them'},
        'queue/disable_new_track_when_playing': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'dis',
                                                 'tooltip': 'Disallow playing new tracks when another track is playing'},
        'queue/remove_item_when_played': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'rem',
                                          'tooltip': 'Remove track from queue upon playback'},
        'player/auto_advance': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'auto',
                                'tooltip': 'Automatically advance to the next track'},
        'player/auto_advance_delay': {'value': None, 'widget': None, 'type': 'spin', 'label': 'delay',
                                      'tooltip': 'Delay between tracks (ms):'}
    }
    """
    Usable options
    """

    def enable(self, exaile):
        """
        Called on startup of exaile
        """
        self._exaile = exaile

        event.add_callback(self._on_option_set, 'playlist_option_set')
        event.add_callback(self._on_option_set, 'queue_option_set')
        event.add_callback(self._on_option_set, 'player_option_set')

    def disable(self, exaile):
        # TODO successfull disabling
        pass

    def _on_option_set(self, event_name, event_source, option: str) -> None:
        if option not in self._options:
            return

        if self._self_triggered:
            self._self_triggered = False
            return

        self._options[option]['value'] = settings.get_option(option)
        if self._options[option]['type'] == 'toggle':
            self._options[option]['widget'].set_active(self._options[option]['value'])
        elif self._options[option]['type'] == 'spin':
            self._options[option]['widget'].get_children()[0].set_value(self._options[option]['value'])

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

    def _get_delay_value(self) -> int:
        """
        Get the current delay value in seconds as int
        """
        value = settings.get_option('player/auto_advance_delay')
        if value == None:
            value = 0
        value = value / 1000
        return int(value)

    def _set_delay_value(self, value: int) -> None:
        """
        Set the delay value in ms
        """
        value = value * 1000
        settings.set_option('player/auto_advance_delay', value)

    def _add_button(self, setting):
        if self._options[setting]['type'] == 'toggle':
            tbs = Gtk.ToggleButton()
            tbs.set_label(self._options[setting]['label'])
            tbs.set_active(self._options[setting]['value'])
            tbs.connect('toggled', self._on_toggle, setting)

        elif self._options[setting]['type'] == 'spin':
            tbs = Gtk.SpinButton()
            tbs.set_adjustment(Gtk.Adjustment(self._get_delay_value(), 0, 60, 1, 0, 0))
            tbs.connect('value-changed', self._on_spin, setting)

        tbs.set_tooltip_text(_(self._options[setting]['tooltip']))
        tbs.show()
        tb = Gtk.ToolItem()
        tb.add(tbs)
        tb.show()

        self._options[setting]['widget'] = tb
        self._toolbar.insert(tb, -1)

    def on_gui_loaded(self):
        """
        Called when the gui is loaded
        Before that there is no status bar
        """
        self._status_bar = self._exaile.gui.builder.get_object('status_bar')
        self._toolbar = Gtk.Toolbar()

        for k in self._options:
            self._options[k]['value'] = settings.get_option(k)
            self._add_button(k)

        self._toolbar.show()
        self._status_bar.pack_start(self._toolbar, False, True, 0)
        self._status_bar.reorder_child(self._toolbar, 0)

    def on_exaile_loaded(self):
        pass

plugin_class = QuickButtons