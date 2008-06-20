from guitest.gtktest import GtkTestCase
from guitest.utils import mainloop_handler
import pygtk, gtk
import xlgui

class BaseTestCase(GtkTestCase):
    
    def setUp(self):
        GtkTestCase.setUp(self)
        self.gui = xlgui.Main(self)
