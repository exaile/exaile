
from gi.repository import Gtk

class QuickButtons:

    def enable(self, exaile):
        self._exaile = exaile
        # status_bar = self._exaile.gui.main.statusbar.status_bar
        # box = status_bar.get_message_area()
        # btn = Gtk.Button('test123')
        # box.pack_end(btn, False, True, 0)
        # pass

    def disable(self, exaile):
        pass

    def on_gui_loaded(self):
        '''- This
        will
        be
        called
        when
        the
        GUI is ready, or
        immediately if already
        done '''

        status_bar = self._exaile.gui.builder.get_object('status_bar')
        box = status_bar.get_message_area()
        btn = Gtk.Button('test123')
        status_bar.pack_end(btn, False, True, 0)

    def on_exaile_loaded(self):
        '''- This
        will
        be
        called
        when
        exaile is done
        loading, or
        immediately if already
        done
    '''
        # status_bar = self._exaile.builder.get_object('status_bar')


    def teardown(self, exaile):
        ''' - This
        will
        be
        called
        when
        exaile is unloading
        '''


plugin_class = QuickButtons