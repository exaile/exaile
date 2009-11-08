try:
    import guitest.gtktest
except ImportError:
    pass

from tests.gui.base import BaseTestCase
from xl import event, track

class DummyPlayer(object):
    pass

class NotifyOsdTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)

        self.plugin = self.load_plugin('notifyosd')
        self.plugin.enable(self)
        self.player = DummyPlayer()
        self.player.current = track.Track()

        self.player.current['title'] = 'Truly'
        self.player.current['artist'] = 'Delerium'
        self.player.current['album'] = 'Chimera'

    def testNotify(self):
        self.plugin.EXAILE_NOTIFYOSD.on_play('',
            self.player, self.player.current)

    def tearDown(self):
        self.plugin.disable(self)

