import unittest
import xl.trax.search as search

class TestSearchResultTrack(unittest.TestCase):

    def test_get_track(self):
        self.search_result_track = search.SearchResultTrack('foo')
        self.assertEqual(self.search_result_track.track, 'foo')

