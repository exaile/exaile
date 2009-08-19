from tests.cover import CoverBaseTestCase
import lastfmcovers

class LastFMCoverTestCase(CoverBaseTestCase):
    def setUp(self):
        CoverBaseTestCase.setUp(self)
        self.cm.add_search_method(lastfmcovers.LastFMCoverSearch())

    def testLastFMCovers(self):
        # amazon doesn't have this cover, so lastfm should return a lastfm url
        # for the cover
        track = {
            'album': 'faith',
            'artist': 'fatali'
        }

        self.cm.set_preferred_order(['lastm'])
        covers = self.cm.find_covers(track)
        assert len(covers) > 0, "Last.fm cover search failed"
