
from gi.repository import Gtk

class QuickButtons:

    def enable(self, exaile):
        self._exaile = exaile

    def disable(self, exaile):
        pass

    def on_gui_loaded(self):
        status_bar = self._exaile.gui.builder.get_object('status_bar')
        area = Gtk.Toolbar()

        newtb = Gtk.ToggleToolButton()
        newtb.set_label('test')

        newtb.show()
        area.insert(newtb, 0)
        area.show()

        status_bar.pack_start(area, False, True, 0)
        status_bar.reorder_child(area, 0)

    def on_exaile_loaded(self):
        pass

plugin_class = QuickButtons