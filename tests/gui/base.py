from guitest.gtktest import GtkTestCase
from guitest.utils import mainloop_handler
import pygtk, gtk
import xlgui
import tests.base
from xl import playlist, radio, player

class FakeRadio(object):
    stations = {}

class BaseTestCase(GtkTestCase, 
    tests.base.BaseTestCase):
    
    def setUp(self):
        self.radio = FakeRadio()
        GtkTestCase.setUp(self)
        tests.base.BaseTestCase.setUp(self)
        self.player = player.get_player()()
        self.queue = player.PlayQueue(self.player)
        self.playlists = playlist.PlaylistManager()
        self.radio = radio.RadioManager()
        self.gui = xlgui.Main(self)
