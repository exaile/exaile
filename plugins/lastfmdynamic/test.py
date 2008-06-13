from tests.base import BaseTestCase
from xl import dynamic, collection

import lastfmdynamic

class LastFMDymamic(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)

        self.dm = dynamic.DynamicManager(collection.Collection('Test'))
        self.plugin = lastfmdynamic.LastfmSource()
        self.dm.add_search_method(self.plugin)

    def testFindSimilarArtists(self):
        
        items = self.dm.find_similar_artists({
            'artist': 'Hooverphonic',
            'album': 'A New Stereophonic Sound Spectacular'
        })

        assert len(items) > 2, "Similar artist search failed"
