import unittest, time, md5
from xl import collection, settings
from base import BaseTestClass

class CollectionTestCase(BaseTestClass):
    def testCount(self):
        tracks = self.collection.search('')
        assert len(tracks) == 5, "Number of tracks scanned is incorrect"

    def testSaveLoad(self):
        self.collection.save_to_location()
        
        # test col
        col = collection.Collection("TestCollection2", self.temp_col_loc)
        tracks = self.collection.search('')
        assert len(tracks) == 5, "Number of tracks scanned is incorrect"

        # test libraries
        l = col.get_libraries()
        assert len(l) == 1, "Number of saved libraries is incorrect"
        assert l[0].location == './tests/data', "Saved library is incorrect"

    def testAllFieldSearch(self):
        c = self.collection

        # search for a keyword in all fields
        tracks = c.search('Black')
        assert len(tracks) == 1, "Keyword search failed"
        assert tracks[0]['title'].find('black') > -1, "Keyword search failed"

    def testNotSearch(self):
        tracks = self.collection.search(
            """
                artist=="TestArtist" NOT album="Second"
            """
        )

        assert len(tracks) == 2, "Not search failed"
