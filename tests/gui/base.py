from guitest.gtktest import GtkTestCase
from guitest.utils import mainloop_handler
import pygtk, gtk
import xlgui
import tests.base

class FakeRadio(object):
    stations = {}

class BaseTestCase(GtkTestCase, 
    tests.base.BaseTestCase):
    
    def setUp(self):
        self.radio = FakeRadio()
        GtkTestCase.setUp(self)
        tests.base.BaseTestCase.setUp(self)
        self.gui = xlgui.Main(self)
