
from gi.repository import Gtk
from xl import event, settings

class QuickButtons:

    def enable(self, exaile):
        self._exaile = exaile
        self._options = {
            'playlist/enqueue_by_default': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'enq'},
            'player/auto_advance_delay': {'value': None, 'widget': None, 'type': 'spin', 'label': 'delay'},
            'queue/disable_new_track_when_playing': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'dis'},
            'queue/remove_item_when_played': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'rem'},
            'player/auto_advance': {'value': None, 'widget': None, 'type': 'toggle', 'label': 'auto'}
        }

        event.add_callback(self._on_option_set, 'playlist_option_set')
        event.add_callback(self._on_option_set, 'queue_option_set')
        event.add_callback(self._on_option_set, 'player_option_set')

    def disable(self, exaile):
        pass

    def _on_option_set(self, event_name, event_source, option):
        if not option in self._options:
            return

        self._options[option]['value'] = settings.get_option(option)
        if self._options[option]['type'] == 'toggle':
            self._options[option]['widget'].set_active(self._options[option]['value'])
        if self._options[option]['type'] == 'spin':
            self._options[option]['widget'].get_children()[0].set_value(self._options[option]['value'])

    def _on_toggle(self, widget, setting):
        settings.set_option(setting, widget.get_active())

    def _on_spin(self, widget, setting):
        pass

    def _get_delay_value(self):
        value = 1

    def _add_button(self, setting):
        if self._options[setting]['type'] == 'toggle':
            tbs = Gtk.ToggleButton()
            tbs.set_label(self._options[setting]['label'])
            tbs.set_active(self._options[setting]['value'])
            tbs.connect('toggled', self._on_toggle, setting)

        elif self._options[setting]['type'] == 'spin':
            tbs = Gtk.SpinButton()
            tbs.set_adjustment(Gtk.Adjustment(value=self._get_delay_value(), lower=0, upper=10, step_incr=1, page_incr=1, page_size=0))
            tbs.connect('value-changed', self._on_spin, setting)

        tbs.show()
        tb = Gtk.ToolItem()
        tb.add(tbs)

        self._options[setting]['widget'] = tb
        tb.show()
        self._toolbar.insert(tb, -1)

    def on_gui_loaded(self):

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