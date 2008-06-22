try:
    import guitest.gtktest
except ImportError:
    pass

from tests.base import BaseTestCase
from xl import event

class DummyPlayer(object):
    pass

class NotifyTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)

        self.plugin = self.load_plugin('notify')
        self.plugin.enable(self)
        self.player = DummyPlayer()
        self.player.current = {
            'title': 'Truly',
            'artist': 'Delerium',
            'album': 'Chimera'
        }

    def testNotify(self):
        self.plugin.on_play('', self.player, self.player.current) 

    def tearDown(self):
        self.plugin.disable(self)

