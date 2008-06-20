from guitest.gtktest import GtkTestCase
import xlgui

class BaseTestCase(GtkTestCase):
    def setUp(self):
        self.gui = xlgui.Main(self)

    def tearDown(self):
        pass
