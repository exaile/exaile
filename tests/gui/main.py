from tests.gui import base

class GUIMainTestCase(base.BaseTestCase):
    def setUp(self):
        base.BaseTestCase.setUp(self)

    def testDefaultSizeAndPos(self):
        window = self.gui.main.window
        (x, y) = window.get_position()
        (width, height) = window.get_size()

        assert x == y == 10, "Default position is incorrect"
        assert height == 600, "Default height is incorrect"
        assert width >= 700 and width < 750, "Default width is incorrect"
        assert height == 600, "Default height is incorrect"
