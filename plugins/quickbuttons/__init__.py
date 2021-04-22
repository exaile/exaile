
from gi.repository import Gtk
from xl import common, event

class QuickButtons:

    def enable(self, exaile):
        self._exaile = exaile


    def disable(self, exaile):
        pass

    def _on_option_set(self, event_name, event_source, option):
        print('option set')

        self._enqueue_by_default = event_source.get_option(option)

        pass

    def on_gui_loaded(self):

        self._enqueue_by_default = None
        name = 'playlist'
        options = {'playlist/enqueue_by_default' : '_enqueue_by_default'}

        self._settings_unsub = common.subscribe_for_settings(name, options, self)
        event.add_callback(self._on_option_set, 'playlist_option_set')


        status_bar = self._exaile.gui.builder.get_object('status_bar')
        area = Gtk.Toolbar()

        # toggle button
        newtb = Gtk.ToggleToolButton()
        newtb.set_label('test')
        newtb.show()
        newtb.set_active(self._enqueue_by_default)
        area.insert(newtb, 0)

        # spinner
        spinbtn = Gtk.SpinButton()
        spinbtn.set_adjustment(Gtk.Adjustment(value=0, lower=0, upper=10, step_incr=1, page_incr=1, page_size=0))
        spinbtn.show()
        spinbtn_toolitem = Gtk.ToolItem()
        spinbtn_toolitem.add(spinbtn)
        spinbtn_toolitem.show()
        area.insert(spinbtn_toolitem, 1)

        '''
        Buttons
        
    Queue tracks by default instead of playing them
    Disallow playing new tracks when another track is playing
    Remove track from queue upon playback
    Automatically advance to the next track
    Delay between tracks (ms)

        '''

        area.show()

        status_bar.pack_start(area, False, True, 0)
        status_bar.reorder_child(area, 0)

    def on_exaile_loaded(self):
        pass

plugin_class = QuickButtons