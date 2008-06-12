from tests.base import BaseTestCase
from tests.cover import CoverBaseTestCase
import amazoncovers

class AmazonCoverTestCase(CoverBaseTestCase):
    def setUp(self):
        CoverBaseTestCase.setUp(self)
        self.cm.add_search_method(amazoncovers.AmazonCoverSearch(
            amazoncovers.AMAZON_KEY))

    def testAmazonCovers(self):
        track = self.collection.search('artist=Delerium')[0]
        self.cm.set_preferred_order(['amazon'])

        covers = self.cm.find_covers(track, limit=2)

        assert len(covers) == 2, "Amazon cover search failed"
