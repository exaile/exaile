from guitest.gtktest import GtkTestCase
from guitest.utils import mainloop_handler
import pygtk, gtk
import xlgui
import tests.base

class BaseTestCase(GtkTestCase, 
    tests.base.BaseTestCase):
    
    def setUp(self):
        GtkTestCase.setUp(self)
        tests.base.BaseTestCase.setUp(self)
        self.gui = xlgui.Main(self)
