from xl import radio
from tests.base import BaseTestCase

class ShoutcastTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)
        self.manager = radio.RadioManager()
        self.radio = self.manager
        self.shoutcast_plugin = self.load_plugin('shoutcast')
        self.shoutcast_plugin.enable(self)

    def testShoutcastSearch(self):
        stations = self.manager.search('shoutcast', 'ravetrax')
        tracks = stations[0].get_playlist().get_tracks()
        assert len(tracks) > 0, "Shoutcast search failed"
